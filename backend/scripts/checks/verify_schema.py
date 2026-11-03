"""Verify the migrated schema matches the committed SQLAlchemy models (validate_schema)."""

from app.infrastructure.models.registry import register_sqlalchemy_models
from config.database import create_sync_db_engine
from config.get_db import validate_schema

# Match the real bootstrap order (bootstrap.py): register every ORM model and
# apply the comment contract before validating against the frozen schema.
register_sqlalchemy_models()

engine = create_sync_db_engine(echo=False)
with engine.connect() as conn:
    validate_schema(conn)
print('validate_schema: OK — schema matches committed models', flush=True)
