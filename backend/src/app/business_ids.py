"""Database-generated numeric business IDs; decimal strings on the wire."""

import hashlib
import json
from copy import deepcopy

from sqlalchemy import BigInteger, Column, Integer, Sequence
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import next_value

from config.database import Base

BUSINESS_ID_TABLES = (
    'categories',
    'collection_runs',
    'data_sources',
    'digest_schedules',
    'generation_tasks',
    'knowledge_files',
    'model_calls',
    'news_articles',
    'papers',
    'report_assets',
    'reports',
    'templates',
)
BUSINESS_ID_SEQUENCE = Sequence('business_id_seq', metadata=Base.metadata)
MAX_BIGINT = 9223372036854775807


@compiles(next_value, 'sqlite')
def _sqlite_next_value(element, compiler, **kwargs):
    # SQLite INTEGER PRIMARY KEY allocates its own value for offline tests.
    return 'NULL'


def business_pk(**kwargs):
    return Column(
        BigInteger().with_variant(Integer, 'sqlite'),
        BUSINESS_ID_SEQUENCE,
        server_default=BUSINESS_ID_SEQUENCE.next_value(),
        primary_key=True,
        **kwargs,
    )


def parse_business_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('资料编号必须为正整数')
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError('资料编号必须为正整数')
    number = int(value)
    if not 1 <= number <= MAX_BIGINT:
        raise ValueError('资料编号超出 bigint 正整数范围')
    return number


def wire_id(value):
    return None if value is None else str(parse_business_id(value))


def generation_request_fingerprint(request, materials):
    """One representation for raw scalar IDs, typed input and stored snapshots.

    Frozen/authorized materials resolve scalar IDs without reloading changed or
    deleted source bodies. Explicitly changing a supplied type still conflicts.
    """
    canonical = deepcopy({key: value for key, value in request.items() if key not in {'request_id', 'requestId'}})
    kinds = {}
    for material in materials:
        identity = wire_id(material['id'])
        kinds.setdefault(identity, set()).add(material['type'])
    references = canonical.pop('materials', None) or canonical.get('selected_item_ids') or []
    canonical.pop('selected_item_ids', None)
    selected = []
    for reference in references:
        if isinstance(reference, dict):
            identity = wire_id(reference['id'])
            kind = reference.get('type')
        else:
            identity = wire_id(reference)
            matches = kinds.get(identity, set())
            kind = next(iter(matches)) if len(matches) == 1 else 'unknown'
        selected.append({'type': kind, 'id': identity})
    canonical['materials'] = selected
    for key in ('template_id', 'report_id'):
        if canonical.get(key) is not None:
            canonical[key] = wire_id(canonical[key])
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
