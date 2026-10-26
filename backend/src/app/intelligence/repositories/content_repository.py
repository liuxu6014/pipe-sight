"""Collected content queries using only canonical columns and bounded SQL pages."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, and_, case, cast, func, literal, or_, select

from app.business_ids import parse_business_id
from app.business_time import BeijingAuditTime, audit_as_utc
from app.intelligence.models.collection import PipelineSource
from app.intelligence.models.content import PipelineArticle, PipelineCategory, PipelinePaper
from app.library.models.materials import PipelineMaterial
from app.research.models.research_models import PipelineReport

SearchCursor = tuple[int, datetime, str, int]


def _contains(value: str) -> str:
    return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def _category_identity(value: Any) -> int | None:
    """A free-text filter may name a category rather than reference its ID."""
    try:
        return parse_business_id(value)
    except ValueError:
        return None


class ContentDao:
    @staticmethod
    def query(model: Any, **filters: Any):
        statement = select(model)
        is_article = model is PipelineArticle
        is_paper = model is PipelinePaper
        is_public = is_article or is_paper
        if is_public:
            statement = statement.outerjoin(PipelineCategory, model.category_id == PipelineCategory.id)
        if is_article:
            statement = statement.join(PipelineSource, model.source_id == PipelineSource.id)
            source_type = filters.get('article_type')
            if source_type:
                statement = statement.where(PipelineSource.type == {'news': 'website'}.get(source_type, source_type))
        if model in {PipelineMaterial, PipelineReport}:
            statement = statement.where(model.user_id == filters['user_id'])
        if is_article:
            values = (model.title, model.content_zh, model.content, model.author)
            date = model.published_at
        elif is_paper:
            values = (model.title, model.title_zh, model.abstract_zh, model.abstract, model.authors)
            date = model.published_date
        elif model is PipelineMaterial:
            values = (model.name, func.coalesce(model.edited_text, model.extracted_text))
            date = model.updated_at
        else:
            values = (model.title, model.content)
            date = model.updated_at
        keyword = (filters.get('keyword') or '').strip()
        if keyword:
            statement = statement.where(or_(*(value.ilike(_contains(keyword), escape='\\') for value in values)))
        category_id = filters.get('category_id')
        if category_id is not None and is_public:
            identity = _category_identity(category_id)
            statement = statement.where(
                or_(PipelineCategory.id == identity, PipelineCategory.name == str(category_id))
                if identity is not None
                else PipelineCategory.name == str(category_id)
            )
        for name in ('tag', 'legacy_tag'):
            category = filters.get(name)
            if category and is_public:
                identity = _category_identity(category)
                statement = statement.where(
                    or_(PipelineCategory.id == identity, PipelineCategory.name == str(category))
                    if identity is not None
                    else PipelineCategory.name == category
                )
        categories = filters.get('tags') or filters.get('directions') or []
        if categories:
            if is_public:
                identities = [identity for value in categories if (identity := _category_identity(value)) is not None]
                statement = statement.where(
                    or_(
                        PipelineCategory.id.in_(identities),
                        PipelineCategory.name.in_([str(value) for value in categories]),
                    )
                )
            else:
                statement = statement.where(
                    or_(*(value.ilike(_contains(term), escape='\\') for term in categories for value in values))
                )
        for key, lower in (
            ('published_from', True),
            ('published_to', False),
            ('updated_from', True),
            ('updated_to', False),
        ):
            boundary = filters.get(key)
            if boundary is not None:
                if is_paper:
                    # A year-only date cannot honestly satisfy a day-level lower bound.
                    # Compare its available precision rather than inventing Jan 1 timestamps.
                    boundary = boundary.strftime('%Y-%m-%d')
                    bound = func.left(boundary, func.length(date))
                else:
                    bound = boundary
                statement = statement.where(date >= bound if lower else date <= bound)
        if is_paper:
            if filters.get('year_from'):
                statement = statement.where(func.left(date, 4) >= str(filters['year_from']))
            if filters.get('year_to'):
                statement = statement.where(func.left(date, 4) <= str(filters['year_to']))
            if filters.get('journal'):
                statement = statement.where(model.journal.ilike(_contains(filters['journal']), escape='\\'))
        return statement, date, values

    @classmethod
    async def _list(cls, db: Any, model: Any, **filters: Any):
        statement, date, values = cls.query(model, **filters)
        keyword = (filters.get('keyword') or '').strip()
        rank = (
            case(
                *[
                    (value.ilike(_contains(keyword), escape='\\'), len(values) - index)
                    for index, value in enumerate(values)
                ],
                else_=0,
            )
            if keyword and (filters.get('ranked', False) or filters.get('search_after') is not None)
            else 0
        )
        # A cursor must use the same score/date/type/id ordering as the merged service.
        kind = {
            PipelineArticle: 'news',
            PipelinePaper: 'paper',
            PipelineMaterial: 'document',
            PipelineReport: 'report',
        }[model]
        if model is PipelinePaper:
            # Compare the technical midnight anchor as an instant, not a date
            # string: truncating a news cursor would skip same-day papers.
            order_date = func.timezone(
                'UTC', cast(func.rpad(func.coalesce(date, '1970'), 10, '-01'), DateTime(timezone=False))
            )
        elif isinstance(date.type, BeijingAuditTime):
            # Audit storage is Beijing wall time. Normalize SQL values before
            # coalescing/comparing with absolute search cursors, independently
            # of the PostgreSQL session TimeZone.
            order_date = func.coalesce(audit_as_utc(date), datetime(1970, 1, 1, tzinfo=timezone.utc))
        else:
            order_date = func.coalesce(date, datetime(1970, 1, 1, tzinfo=timezone.utc))
        cursor = filters.get('search_after')
        if cursor:
            score, cursor_date, cursor_kind, identity = cursor
            identity = parse_business_id(identity)
            # Match numeric ID ordering used by the cross-type cursor.
            statement = statement.where(
                or_(
                    rank < score if not isinstance(rank, int) else (rank < score),
                    and_(
                        rank == score,
                        or_(
                            order_date < cursor_date,
                            and_(
                                order_date == cursor_date,
                                or_(kind < cursor_kind, and_(kind == cursor_kind, model.id < identity)),
                            ),
                        ),
                    ),
                )
            )
        if not isinstance(rank, int):
            statement = statement.order_by(rank.desc())
        statement = statement.order_by(order_date.desc(), model.id.desc())
        if filters.get('ranked', False) or cursor is not None:
            statement = statement.add_columns(
                (literal(rank) if isinstance(rank, int) else rank).label('_search_rank'),
                order_date.label('_search_cursor_date'),
            )
            result = await db.execute(statement.offset(filters.get('offset', 0)).limit(filters.get('limit', 20)))
            items = []
            for item, score, instant in result.all():
                item._search_rank, item._search_cursor_date = int(score), instant
                items.append(item)
            return items
        return (
            (await db.execute(statement.offset(filters.get('offset', 0)).limit(filters.get('limit', 20))))
            .scalars()
            .all()
        )

    @classmethod
    async def _count(cls, db: Any, model: Any, **filters: Any):
        statement, _, _ = cls.query(model, **filters)
        return (await db.execute(select(func.count()).select_from(statement.subquery()))).scalar_one()

    @classmethod
    async def list_articles(cls, db: Any, **filters: Any):
        return await cls._list(db, PipelineArticle, **filters)

    @classmethod
    async def count_articles(cls, db: Any, **filters: Any):
        return await cls._count(db, PipelineArticle, **filters)

    @classmethod
    async def list_papers(cls, db: Any, **filters: Any):
        return await cls._list(db, PipelinePaper, **filters)

    @classmethod
    async def count_papers(cls, db: Any, **filters: Any):
        return await cls._count(db, PipelinePaper, **filters)

    @staticmethod
    async def get_article(db: Any, identity: str):
        return await db.get(PipelineArticle, parse_business_id(identity))

    @staticmethod
    async def get_paper(db: Any, identity: str):
        return await db.get(PipelinePaper, parse_business_id(identity))

    @classmethod
    async def list_search_materials(cls, db: Any, user_id: int, **filters: Any):
        return await cls._list(db, PipelineMaterial, user_id=user_id, **filters)

    @classmethod
    async def count_search_materials(cls, db: Any, user_id: int, **filters: Any):
        return await cls._count(db, PipelineMaterial, user_id=user_id, **filters)

    @classmethod
    async def list_search_reports(cls, db: Any, user_id: int, **filters: Any):
        return await cls._list(db, PipelineReport, user_id=user_id, **filters)

    @classmethod
    async def count_search_reports(cls, db: Any, user_id: int, **filters: Any):
        return await cls._count(db, PipelineReport, user_id=user_id, **filters)

    @staticmethod
    async def portal_overview_counts(db: Any, *, user_id: int, start: datetime, end: datetime):
        # One round trip; every aggregate describes the same database statement snapshot.
        expressions = []
        for kind, source_type in (('news', 'website'), ('wechat', 'wechat')):
            count = (
                select(func.count())
                .select_from(PipelineArticle)
                .join(PipelineSource)
                .where(PipelineSource.type == source_type)
            )
            expressions.append(count.scalar_subquery().label(f'{kind}_count'))
            expressions.append(
                count.where(PipelineArticle.created_at >= start, PipelineArticle.created_at < end)
                .scalar_subquery()
                .label(f'today_{kind}_count')
            )
        expressions.extend(
            [
                select(func.count()).select_from(PipelinePaper).scalar_subquery().label('paper_count'),
                select(func.count())
                .select_from(PipelinePaper)
                .where(PipelinePaper.created_at >= start, PipelinePaper.created_at < end)
                .scalar_subquery()
                .label('today_paper_count'),
                select(func.count())
                .select_from(PipelineReport)
                .where(PipelineReport.user_id == user_id)
                .scalar_subquery()
                .label('report_count'),
            ]
        )
        result = dict((await db.execute(select(*expressions))).mappings().one())
        result['today_added_count'] = sum(result[f'today_{kind}_count'] for kind in ('paper', 'news', 'wechat'))
        return result
