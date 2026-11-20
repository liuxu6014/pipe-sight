"""ClamD INSTREAM client. File bytes stay on the configured private scanner network."""

import argparse
import os
import socket
import struct
from pathlib import Path

MAX_RESPONSE_BYTES = 4096


def scan_file(path: Path | None, *, host: str, port: int, timeout: float = 25) -> tuple[int, str]:
    """Return clamdscan-compatible exit codes: clean=0, infected=1, unavailable=2."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            if path is None:
                client.sendall(b'zPING\0')
            else:
                with path.open('rb') as source:
                    client.sendall(b'zINSTREAM\0')
                    while chunk := source.read(65536):
                        client.sendall(struct.pack('!I', len(chunk)) + chunk)
                    client.sendall(struct.pack('!I', 0))
            result = bytearray()
            while len(result) < MAX_RESPONSE_BYTES:
                chunk = client.recv(512)
                if not chunk:
                    break
                result.extend(chunk)
                if b'\0' in chunk or b'\n' in chunk:
                    break
        text = bytes(result).split(b'\0')[0].decode('utf-8', errors='replace').strip()
        if (path is None and text == 'PONG') or (path is not None and text == 'stream: OK'):
            return 0, text
        if path is not None and text.startswith('stream: ') and text.endswith(' FOUND'):
            return 1, '扫描发现风险文件'
        return 2, '扫描器未返回有效结果'
    except (OSError, ValueError):
        return 2, '扫描器不可用，请检查连接、病毒库和文件权限'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path)
    parser.add_argument('--ping', action='store_true')
    args = parser.parse_args()
    if not args.ping and args.path is None:
        parser.error('需要文件路径或 --ping')
    try:
        code, message = scan_file(
            None if args.ping else args.path,
            host=os.getenv('FILE_SCAN_HOST', 'pipesight-clamav'),
            port=int(os.getenv('FILE_SCAN_PORT', '3310')),
            timeout=float(os.getenv('FILE_SCAN_SOCKET_TIMEOUT', '25')),
        )
    except ValueError:
        code, message = 2, '扫描器连接配置无效'
    print(message)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
