"""A shared-volume heartbeat, independent of API and database readiness."""

import asyncio
import json
import math
import os
import time
from pathlib import Path
from uuid import uuid4

HEARTBEAT_INTERVAL = 10
HEARTBEAT_MAX_AGE = 45
MAX_FUTURE_SKEW = 5
QUEUE_MAX_AGE = 120
EXPECTED_QUEUES = ('research', 'digest', 'exports', 'materials', 'export_cleanup')
_queue_scans: dict[str, dict] = {}


def queue_scan_result(name: str, *, success: bool) -> None:
    previous = _queue_scans.get(name, {})
    _queue_scans[name] = {
        'ok': success,
        'lastSuccess': time.time() if success else previous.get('lastSuccess'),
    }


def _queue_healthy(record: object, now: float) -> bool:
    if not isinstance(record, dict) or record.get('ok') is not True:
        return False
    try:
        age = now - float(record['lastSuccess'])
        return math.isfinite(age) and -MAX_FUTURE_SKEW <= age <= QUEUE_MAX_AGE
    except (KeyError, TypeError, ValueError):
        return False


def heartbeat_path() -> Path:
    return Path(os.getenv('TASK_WORKER_HEARTBEAT_PATH', 'vf_admin/task-worker/heartbeat.json'))


def worker_status(*, path: Path | None = None, now: float | None = None) -> dict:
    try:
        data = json.loads((path or heartbeat_path()).read_text())
        age = (time.time() if now is None else now) - float(data['at'])
        if data.get('status') != 'running' or not -MAX_FUTURE_SKEW <= age <= HEARTBEAT_MAX_AGE:
            return {'status': 'unavailable', 'reason': 'heartbeat_expired'}
        # A living heartbeat alone cannot prove that the queue scans progress.
        # Missing/malformed queue records fail closed, including old heartbeats.
        queues = data.get('queues')
        queues = queues if isinstance(queues, dict) else {}
        check_time = time.time() if now is None else now
        failed = [name for name in EXPECTED_QUEUES if not _queue_healthy(queues.get(name), check_time)]
        if failed:
            return {'status': 'unavailable', 'reason': 'queue_scan_failed', 'queues': failed}
        return {'status': 'ok', 'lastSeenSeconds': max(0, round(age))}
    except (OSError, ValueError, TypeError, KeyError):
        return {'status': 'unavailable', 'reason': 'heartbeat_missing'}


async def run_worker_heartbeat(stop_event: asyncio.Event) -> None:
    path = heartbeat_path()
    owner = uuid4().hex
    temporary = path.with_name(path.name + '.' + owner)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        while not stop_event.is_set():
            temporary.write_text(
                json.dumps({'at': time.time(), 'owner': owner, 'status': 'running', 'queues': _queue_scans})
            )
            temporary.replace(path)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                pass
    finally:
        temporary.unlink(missing_ok=True)
        try:
            if json.loads(path.read_text()).get('owner') == owner:
                path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            pass
