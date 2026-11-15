"""Bounded generation capacity; queue claims enforce the same limits across workers."""

import os


def _limit(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, min(value, maximum))


RESEARCH_GLOBAL_LIMIT = _limit('RESEARCH_GLOBAL_CONCURRENCY', 4, 64)
RESEARCH_USER_LIMIT = _limit('RESEARCH_USER_CONCURRENCY', 2, RESEARCH_GLOBAL_LIMIT)
RESEARCH_MODEL_LIMIT = _limit('RESEARCH_MODEL_CONCURRENCY', 2, RESEARCH_GLOBAL_LIMIT)
RESEARCH_DISPATCH_BATCH = _limit('RESEARCH_DISPATCH_BATCH', 40, 200)
EXPORT_CONCURRENCY = _limit('REPORT_EXPORT_CONCURRENCY', 2, 16)
# One transaction lock serializes the count-and-claim decision in PostgreSQL.
RESEARCH_CAPACITY_LOCK = 720260115
