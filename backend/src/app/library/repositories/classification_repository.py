"""Atomic, bounded claims and token-fenced results for document classification."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import Row, func, select, text, update

from app.business_ids import parse_business_id
from app.intelligence.models.categories import PipelineCategory
from app.library.classification_state import CLASSIFICATION_CONSENT, SUPERSEDED_MESSAGE
from app.library.models.materials import PipelineMaterial as Material
from app.library.models.materials import utcnow
from app.library.repositories.material_repository import _dialect_name

CLASSIFICATION_CONCURRENCY = 2
CAPACITY_LOCK = 720261120
INTERRUPTED_MESSAGE = '分类执行中断，模型结果无法确认；为避免重复调用，请手动重试分类'


class MaterialClassificationDao:
    @staticmethod
    async def ready(db) -> list[int]:
        # A paid call interrupted by a worker failure is never automatically replayed.
        await db.execute(
            update(Material)
            .where(
                Material.classification_status == 'running',
                Material.classification_updated_at < utcnow() - timedelta(minutes=15),
            )
            .values(classification_status='failed', classification_error=INTERRUPTED_MESSAGE, classification_token=None)
        )
        # Old queued rows have no owner consent and must never leave the server.
        await db.execute(
            update(Material)
            .where(Material.classification_status == 'queued', Material.classification_token.is_(None))
            .values(classification_status='not_configured')
        )
        await db.commit()
        return list(
            await db.scalars(
                select(Material.id)
                .where(
                    Material.status == 'ready',
                    Material.classification_status == 'queued',
                    Material.classification_token == CLASSIFICATION_CONSENT,
                )
                .order_by(Material.id)
                .limit(20)
            )
        )

    @staticmethod
    async def claim(db, identity) -> tuple[str, Row] | None:
        if _dialect_name(db) == 'postgresql':
            await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': CAPACITY_LOCK})
        active = (
            select(func.count())
            .select_from(Material)
            .where(Material.classification_status == 'running')
            .correlate(None)
        )
        token = uuid4().hex
        result = await db.execute(
            update(Material)
            .where(
                Material.id == parse_business_id(identity),
                Material.status == 'ready',
                Material.classification_status == 'queued',
                Material.classification_token == CLASSIFICATION_CONSENT,
                active.scalar_subquery() < CLASSIFICATION_CONCURRENCY,
            )
            .values(
                classification_status='running',
                classification_token=token,
                classification_error=None,
                classification_updated_at=utcnow(),
            )
            .returning(
                Material.id,
                Material.name,
                Material.version,
                Material.edited_text,
                Material.extracted_text,
                Material.storage_key,
                Material.filename,
            )
            .execution_options(synchronize_session=False)
        )
        row = result.first()
        await db.commit()
        return (token, row) if row else None

    @staticmethod
    async def is_current(db, identity, *, token, version) -> bool:
        return bool(
            await db.scalar(
                select(Material.id).where(
                    Material.id == parse_business_id(identity),
                    Material.status == 'ready',
                    Material.classification_status == 'running',
                    Material.classification_token == token,
                    Material.version == version,
                    Material.classification_error.is_(None),
                )
            )
        )

    @staticmethod
    async def finish(db, identity, *, token, status, category_id=None, error=None, expected_version=None) -> bool:
        row = await db.scalar(
            select(Material)
            .where(
                Material.id == parse_business_id(identity),
                Material.classification_status == 'running',
                Material.classification_token == token,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return False
        changed = (
            row.classification_error == SUPERSEDED_MESSAGE
            or (expected_version is not None and row.version != expected_version)
            or row.status != 'ready'
        )
        if changed:
            # Release the OLD call only when it has settled. Never automatically
            # replay an interrupted/failed provider attempt, even after an edit.
            if status in {'completed', 'not_configured'}:
                row.classification_status = 'not_configured'
                row.classification_error = None
            else:
                row.classification_status, row.classification_error = 'failed', error
            row.category_id, row.classification_token = None, None
            if row.status == 'parsing':
                # Old/hot-upgrade workers may already be parsing this row. Our
                # write invalidates their xmin fence, so explicitly queue a
                # fresh (non-paid) parse instead of leaving a stranded parser.
                row.status = 'queued'
            row.classification_updated_at = utcnow()
            await db.commit()
            return False
        if category_id is not None:
            category = await db.scalar(
                select(PipelineCategory).where(PipelineCategory.id == category_id).with_for_update()
            )
            if not category or not category.is_enabled or category.applies_to not in {'document', 'all'}:
                status, category_id, error = 'failed', None, '类别规则已变化，请重试分类'
        result = await db.execute(
            update(Material)
            .where(
                Material.id == parse_business_id(identity),
                Material.classification_status == 'running',
                Material.classification_token == token,
            )
            .values(
                category_id=category_id,
                classification_status=status,
                classification_error=error,
                classification_token=None,
                classification_updated_at=utcnow(),
            )
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        return bool(result.rowcount)
