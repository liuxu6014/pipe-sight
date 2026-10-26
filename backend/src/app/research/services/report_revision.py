"""Opaque report-state revision, stable across second-precision DB round trips."""

import hashlib
import json
from typing import Any

from app.business_time import format_business_time

REPORT_FIELDS = ('id', 'user_id', 'title', 'type', 'template_id', 'content', 'version', 'created_at', 'updated_at')


def report_revision(report: Any) -> str:
    state = {field: getattr(report, field, None) for field in REPORT_FIELDS}
    for field in ('id', 'user_id', 'template_id'):
        state[field] = str(state[field]) if state[field] is not None else None
    for field in ('created_at', 'updated_at'):
        state[field] = format_business_time(state[field])
    payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return 'report-v1:' + hashlib.sha256(payload).hexdigest()
