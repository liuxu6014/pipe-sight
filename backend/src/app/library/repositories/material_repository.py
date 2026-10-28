"""资料权限与并发；解析不更新 edited_text 或 version。"""

import re
from typing import Any
from uuid import uuid4

from sqlalchemy import Integer, Text, cast, func, literal_column, select, text, update

from app.business_ids import parse_business_id
from app.library.models.materials import PipelineMaterial as Material
from app.library.models.materials import utcnow


def _dialect_name(db: Any) -> str:
    session = getattr(db, 's', db)  # Offline AsyncMemory wraps a synchronous Session.
    return session.get_bind().dialect.name


async def _sqlite_parse_token(db: Any) -> str:
    """Conservative offline fencing: any local/other-connection write invalidates it.

    This is deliberately stricter than PG row xmin, never a timestamp fallback.
    A different pooled connection also fails closed instead of guessing a token.
    """
    connection = db.s.connection() if hasattr(db, 's') else await db.connection()
    identity = connection.info.setdefault('material_parse_connection', uuid4().hex)
    changes, version = (await db.execute(text(
        'SELECT total_changes(), (SELECT data_version FROM pragma_data_version)'
    ))).one()
    return f'sqlite:{identity}:{changes}:{version}'


class MaterialDao:
    @staticmethod
    async def find_duplicate_upload(db, user_id, file_hash):
        # Serialize uploads of identical bytes per owner across API processes.
        # No global/cross-owner lookup, and edited documents remain independent.
        if _dialect_name(db) == 'postgresql':
            import hashlib
            key = int.from_bytes(hashlib.sha256(f'material:{user_id}:{file_hash}'.encode()).digest()[:8], 'big', signed=True)
            await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
        query = select(Material).where(
            Material.user_id == user_id, Material.hash == file_hash, Material.edited_text.is_(None)
        ).order_by((Material.status == 'ready').desc(), Material.id.asc()).limit(1)
        return await db.scalar(query.execution_options(populate_existing=True))

    @staticmethod
    async def add_material(db, material):
        db.add(material)
        await db.flush()

    @staticmethod
    async def list_accessible_materials(db, user_id, file_ids=None):
        query = select(Material).where(Material.user_id == user_id)
        if file_ids is not None:
            query = query.where(Material.id.in_([parse_business_id(i) for i in file_ids]))
        return list(await db.scalars(query.order_by(Material.updated_at.desc())))

    @staticmethod
    async def get_owned_material(db, material_id, user_id, *, lock=False):
        material_id = parse_business_id(material_id)
        query = select(Material).where(Material.id == material_id, Material.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return await db.scalar(query.execution_options(populate_existing=True))

    get_accessible_material = get_owned_material

    @staticmethod
    async def list_material_ids_for_dispatch(db, **_):
        return list(await db.scalars(select(Material.id).where(Material.status == 'queued')))

    @staticmethod
    async def claim_material_parse(db, material_id, **_):
        material_id = parse_business_id(material_id)
        # RETURNING captures the claimed row and its version atomically. Never
        # reload after committing: that could pick up a later worker's attempt.
        dialect = _dialect_name(db)
        if dialect not in {'postgresql', 'sqlite'}:
            raise RuntimeError('Material parsing requires PostgreSQL row-version fencing')
        now = utcnow()
        statement = (
            update(Material)
            .where(Material.id == material_id, Material.status == 'queued')
            .values(status='parsing', error=None, updated_at=now)
            .execution_options(populate_existing=True)
        )
        if dialect == 'postgresql':
            result = await db.execute(statement.returning(Material, cast(literal_column('xmin'), Text)))
            claimed = result.first()
            row = claimed[0] if claimed else None
            token = f'pg:{claimed[1]}' if claimed else None
        else:
            row = (await db.execute(statement.returning(Material))).scalars().first()
            token = await _sqlite_parse_token(db) if row is not None else None
        await db.commit()
        if row is not None:
            row._parse_token = token
        return row

    @staticmethod
    async def finish_material_parse(db, material_id, *, parse_token, status, extracted_text, error=None):
        material_id = parse_business_id(material_id)
        if not isinstance(parse_token, str):
            return False
        dialect = _dialect_name(db)
        if dialect == 'postgresql' and re.fullmatch(r'pg:[0-9]+', parse_token):
            guard = cast(literal_column('xmin'), Text) == parse_token[3:]
        elif dialect == 'sqlite' and re.fullmatch(r'sqlite:[0-9a-f]{32}:[0-9]+:[0-9]+', parse_token):
            if await _sqlite_parse_token(db) != parse_token:
                return False
            _, _, changes, version = parse_token.split(':')
            # Recheck in the UPDATE itself, not only before its await boundary.
            guard = (func.total_changes() == int(changes)) & (
                select(literal_column('data_version', Integer)).select_from(
                    text('pragma_data_version')
                ).scalar_subquery() == int(version)
            )
        else:
            return False
        result = await db.execute(
            update(Material)
            .where(Material.id == material_id, Material.status == 'parsing', guard)
            .values(status=status, extracted_text=extracted_text, error=error, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        return bool(result.rowcount)
