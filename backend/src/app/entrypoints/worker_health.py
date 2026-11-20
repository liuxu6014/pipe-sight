"""Container health probe: never starts a worker or dispatches jobs."""

import json

from app.health.worker import worker_status


def main() -> None:
    status = worker_status()
    print(json.dumps(status))
    raise SystemExit(0 if status['status'] == 'ok' else 1)


if __name__ == '__main__':
    main()
