"""Beijing, seconds-only audit storage with UTC-aware internal datetime values.

created_at/updated_at and digest dispatch summaries use this type. Lease,
publication and next-schedule instants retain their timezone-aware types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import TypeDecorator

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect
    from sqlalchemy.sql.compiler import SQLCompiler
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.types import TypeEngine

BEIJING = ZoneInfo('Asia/Shanghai')


def _beijing_naive(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError('Business audit time requires a datetime')
    local = value.astimezone(BEIJING) if value.tzinfo is not None else value
    return local.replace(tzinfo=None, microsecond=0)


def audit_now() -> datetime:
    """Client audit default; absolute UTC, truncated rather than rounded."""
    return datetime.now(timezone.utc).replace(microsecond=0)


class BeijingAuditTime(TypeDecorator[datetime]):
    """PG timestamp(0) Beijing wall clock; Python values read back as UTC."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[datetime]:
        kind = TIMESTAMP(timezone=False, precision=0) if dialect.name == 'postgresql' else DateTime(timezone=False)
        return dialect.type_descriptor(kind)

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return _beijing_naive(value) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        local = value.replace(tzinfo=BEIJING) if value.tzinfo is None else value
        return local.astimezone(timezone.utc).replace(microsecond=0)


def format_business_time(value: datetime | str | None, empty: str | None = '') -> str | None:
    """HTTP/display boundary; naive values explicitly mean Beijing, never UTC."""
    if value is None or value == '':
        return empty
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return _beijing_naive(parsed).isoformat(sep=' ', timespec='seconds')


class _ServerNow(FunctionElement[datetime]):
    type = BeijingAuditTime()
    inherit_cache = True


@compiles(_ServerNow)
@compiles(_ServerNow, 'postgresql')
def _compile_server_now(element: _ServerNow, compiler: SQLCompiler, **kwargs: object) -> str:
    return "date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')"


@compiles(_ServerNow, 'sqlite')
def _compile_server_now_sqlite(element: _ServerNow, compiler: SQLCompiler, **kwargs: object) -> str:
    return "datetime('now','+8 hours')"


def server_now() -> _ServerNow:
    """Session-timezone-independent database audit default."""
    return _ServerNow()


class _AuditAsUTC(FunctionElement[datetime]):
    type = DateTime(timezone=True)
    inherit_cache = True


@compiles(_AuditAsUTC)
@compiles(_AuditAsUTC, 'postgresql')
def _compile_audit_utc(element: _AuditAsUTC, compiler: SQLCompiler, **kwargs: object) -> str:
    return f"({compiler.process(element.clauses, **kwargs)} AT TIME ZONE 'Asia/Shanghai')"


@compiles(_AuditAsUTC, 'sqlite')
def _compile_audit_utc_sqlite(element: _AuditAsUTC, compiler: SQLCompiler, **kwargs: object) -> str:
    # Match SQLite DateTime binds exactly, including same-second cursor equality.
    return f"(datetime({compiler.process(element.clauses, **kwargs)}, '-8 hours') || '.000000')"


def audit_as_utc(value: ColumnElement[datetime]) -> _AuditAsUTC:
    """Use an audit column beside an absolute instant without implicit casts."""
    return _AuditAsUTC(value)
