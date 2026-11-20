#!/usr/bin/env python3
"""Exercise deployment boundaries using synthetic files and an isolated network.

Requires pre-existing local frontend/backend images; never builds the real
backend context, reads application .env files, publishes ports, or calls the
actual API/model. Temporary containers/network and generated files are cleaned
up. The evidence JSON is the only retained artifact.

Usage: python3 scripts/checks/verify_deployment_boundary.py --slow-seconds 65
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = """
import json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
class Handler(BaseHTTPRequestHandler):
    def reply(self, payload):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        received = len(self.rfile.read(size))
        self.reply({'probe': 'synthetic-only', 'receivedBytes': received, 'path': self.path})
    def do_GET(self):
        query = parse_qs(urlsplit(self.path).query)
        delay = int(query.get('delay', ['0'])[0])
        time.sleep(delay)
        self.reply({'probe': 'synthetic-only', 'delaySeconds': delay, 'path': self.path})
    def log_message(self, *_args): pass
ThreadingHTTPServer(('0.0.0.0', 9099), Handler).serve_forever()
"""


def docker(*args: str, timeout: float = 30) -> str:
    result = subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True, timeout=timeout
    )
    return result.stdout.strip()


def context_check(temp: Path) -> dict:
    context, destination = temp / "context", temp / "context-result"
    context.mkdir()
    (context / ".dockerignore").write_bytes(
        (ROOT / "backend/.dockerignore").read_bytes()
    )
    (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context/\n")
    excluded = [
        ".env",
        ".env.dev",
        ".env.dockerpg",
        ".runtime/state.json",
        "nested/.env.test",
        "nested/.runtime/state.json",
        "backups/snapshot.txt",
        "backup/snapshot.txt",
        "root-snapshot.sql",
        "database.dump",
    ]
    retained = ["src/audit_stub.py", "sql/current.sql", "sql/legacy/initial.sql"]
    for name in [*excluded, *retained]:
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SYNTHETIC AUDIT SENTINEL ONLY\n")
    docker(
        "build",
        "--quiet",
        "--output",
        f"type=local,dest={destination}",
        str(context),
        timeout=60,
    )
    exported = destination / "context"
    leaked = [name for name in excluded if (exported / name).exists()]
    missing = [name for name in retained if not (exported / name).is_file()]
    return {
        "passed": not leaked and not missing,
        "unexpectedlyIncluded": leaked,
        "requiredFilesMissing": missing,
        "excludedProbes": excluded,
        "retainedProbes": retained,
    }


def request(
    frontend: str, path: str, *, upload: bool, delay: int = 0
) -> tuple[dict, float]:
    assert re.fullmatch(r"/(?:pipesight/)?docker-api/[a-z-]+(?:\?delay=\d+)?", path)
    body = (
        'printf "POST %s HTTP/1.1\\r\\nHost: localhost\\r\\nContent-Length: 2097152\\r\\n'
        'Content-Type: application/octet-stream\\r\\nConnection: close\\r\\n\\r\\n" "$1" >&3; '
        "cat /audit/upload.bin >&3; "
        if upload
        else 'printf "GET %s HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n" "$1" >&3; '
    )
    started = time.monotonic()
    response = docker(
        "exec",
        frontend,
        "bash",
        "-c",
        "exec 3<>/dev/tcp/127.0.0.1/80; " + body + "cat <&3",
        "request",
        path,
        timeout=max(30, delay + 30),
    )
    elapsed = time.monotonic() - started
    # Docker's text transport normalizes CRLF; the synthetic upstream always
    # supplies Content-Length so there is no chunked encoding to decode.
    headers, payload = response.split("\n\n", 1)
    assert headers.splitlines()[0] == "HTTP/1.1 200 OK", response[:500]
    result = json.loads(payload)
    assert result["probe"] == "synthetic-only"
    return result, elapsed


def nginx_check(temp: Path, frontend_image: str, backend_image: str, slow: int) -> dict:
    suffix = uuid.uuid4().hex[:12]
    network, upstream, frontend = (
        f"pipesight-boundary-{kind}-{suffix}" for kind in ["net", "upstream", "nginx"]
    )
    for image in [frontend_image, backend_image]:
        docker("image", "inspect", image, "--format", "{{.Id}}")
    (temp / "upstream.py").write_text(UPSTREAM)
    (temp / "postgres.conf").write_bytes(
        (ROOT / "deploy/nginx/postgres.conf").read_bytes()
    )
    (temp / "nginx.conf").write_text(
        "pid /tmp/nginx.pid; error_log /dev/stderr warn; events {}\n"
        "http { access_log /dev/stdout; include /audit/postgres.conf; }\n"
    )
    (temp / "upload.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    mount = f"{temp}:/audit:ro"
    created = []
    network_created = False
    try:
        docker("network", "create", "--internal", network)
        network_created = True
        docker(
            "run",
            "--rm",
            "-d",
            "--pull=never",
            "--read-only",
            "--network",
            network,
            "--network-alias",
            "ruoyi-backend-pg",
            "--name",
            upstream,
            "-v",
            mount,
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "--entrypoint",
            "python",
            backend_image,
            "-u",
            "/audit/upstream.py",
        )
        created.append(upstream)
        for attempt in range(20):
            try:
                docker(
                    "exec",
                    upstream,
                    "python",
                    "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9099/health',timeout=1).read()",
                    timeout=3,
                )
                break
            except subprocess.CalledProcessError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
        docker(
            "run",
            "--rm",
            "-d",
            "--pull=never",
            "--read-only",
            "--network",
            network,
            "--name",
            frontend,
            "-v",
            mount,
            "--tmpfs",
            "/var/cache/nginx",
            "--tmpfs",
            "/tmp",
            "--entrypoint",
            "nginx",
            frontend_image,
            "-c",
            "/audit/nginx.conf",
            "-g",
            "daemon off;",
        )
        created.append(frontend)
        docker("exec", frontend, "nginx", "-t", "-c", "/audit/nginx.conf")
        uploads = []
        for prefix in ["/docker-api/", "/pipesight/docker-api/"]:
            result, elapsed = request(frontend, prefix + "upload-test", upload=True)
            assert (
                result["receivedBytes"] == 2 * 1024 * 1024
                and result["path"] == "/upload-test"
            )
            uploads.append(
                {
                    "prefix": prefix,
                    "receivedBytes": result["receivedBytes"],
                    "elapsedSeconds": round(elapsed, 3),
                }
            )
        print(
            json.dumps({"stage": "uploads", "passed": True, "results": uploads}),
            flush=True,
        )
        result, elapsed = request(
            frontend, f"/docker-api/slow-test?delay={slow}", upload=False, delay=slow
        )
        assert result["delaySeconds"] == slow and elapsed >= slow
        return {
            "passed": True,
            "uploads": uploads,
            "slowRequest": {
                "delaySeconds": slow,
                "elapsedSeconds": round(elapsed, 3),
                "status": 200,
            },
            "hostPortsPublished": False,
            "realApiOrModelCalled": False,
        }
    finally:
        for name in reversed(created):
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                check=False,
                timeout=15,
            )
        if network_created:
            subprocess.run(
                ["docker", "network", "rm", network],
                capture_output=True,
                check=False,
                timeout=15,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-image", default="ruoyi-frontend:latest")
    parser.add_argument("--backend-image", default="ruoyi-backend-pg:latest")
    parser.add_argument("--slow-seconds", type=int, default=65)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output/full-system-audit-20261120/deployment-boundary.json",
    )
    args = parser.parse_args()
    if not 61 <= args.slow_seconds <= 150:
        parser.error(
            "--slow-seconds must be between 61 and 150 to verify the former 60-second boundary"
        )
    evidence = {
        "configuration": "deploy/nginx/postgres.conf + backend/.dockerignore",
        "syntheticOnly": True,
    }
    with tempfile.TemporaryDirectory(prefix="pipesight-boundary-") as directory:
        temp = Path(directory)
        evidence["buildContext"] = context_check(temp)
        print(
            json.dumps({"stage": "buildContext", **evidence["buildContext"]}),
            flush=True,
        )
        evidence["nginx"] = nginx_check(
            temp, args.frontend_image, args.backend_image, args.slow_seconds
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "stage": "finished",
                "passed": all(
                    evidence[key]["passed"] for key in ["buildContext", "nginx"]
                ),
                "evidence": str(args.output),
            }
        ),
        flush=True,
    )
    if not all(evidence[key]["passed"] for key in ["buildContext", "nginx"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
