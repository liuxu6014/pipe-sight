"""Application-wide SQLAlchemy model registration.

Alembic discovers models separately, but the API process does not execute that
discovery. Importing every persistence module before handling requests is
therefore part of the application bootstrap contract.
"""

# Import for model-registration side effects. Keep this list explicit so a new
# model cannot silently depend on a route import order.
from sqlalchemy import MetaData

from app.infrastructure.models import audit, jobs  # noqa: F401
from app.intelligence.models import ai_models, pipeline_models  # noqa: F401
from app.library.models import materials  # noqa: F401
from app.research.models import research_models  # noqa: F401
from app.schema_comments import COLUMN_COMMENTS, TABLE_COMMENTS
from app.system import models as system_models  # noqa: F401
from config.database import Base


def apply_metadata_comments(metadata: MetaData) -> None:
    """Apply runtime compact-v4 comments without changing types or fields."""
    tables = [table for table in metadata.tables.values() if table.schema in (None, 'public')]
    # Validate every field before altering any comment, including optional
    # framework tables registered by a scheduler after bootstrap.
    for table in tables:
        if table.name not in COLUMN_COMMENTS or set(table.c.keys()) != set(COLUMN_COMMENTS[table.name]):
            raise ValueError(f'表字段与中文注释契约不一致：{table.name}')
    for table in tables:
        table.comment = TABLE_COMMENTS[table.name]
        for column in table.c:
            column.comment = COLUMN_COMMENTS[table.name][column.name]


def register_sqlalchemy_models() -> None:
    """Ensure all application ORM modules have been imported."""
    apply_metadata_comments(Base.metadata)


__all__ = ['apply_metadata_comments', 'register_sqlalchemy_models']
