"""Owner-scoped template management pages; never fetch every prompt for one page."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import defer

from app.intelligence.models.configuration import PipelineTemplateVersion as Template


class TemplateListDao:
    @staticmethod
    async def page(
        db,
        *,
        user_id,
        purpose=None,
        report_type=None,
        keyword='',
        status='all',
        published_only=False,
        page=1,
        page_size=10,
    ) -> tuple:
        filters = [
            or_(
                Template.purpose != 'digest',
                and_(
                    Template.digest_cadence.in_(('weekly', 'monthly', 'all')),
                    or_(Template.preset_key.is_(None), ~Template.preset_key.startswith('digest-fixed-v1-')),
                ),
            )
        ]
        if user_id is not None:
            filters.append(Template.user_id == user_id)
        if purpose:
            filters.append(Template.purpose == purpose)
        filters.append(Template.deleted_at.is_not(None) if status == 'deleted' else Template.deleted_at.is_(None))
        if published_only or status == 'enabled':
            filters.append(Template.is_enabled.is_(True))
        elif status == 'disabled':
            filters.append(Template.is_enabled.is_(False))
        if keyword.strip():
            filters.append(
                or_(
                    Template.name.contains(keyword.strip(), autoescape=True),
                    Template.description.contains(keyword.strip(), autoescape=True),
                )
            )
        counts_query = (
            select(Template.purpose, Template.report_type, func.count())
            .where(*filters)
            .group_by(Template.purpose, Template.report_type)
        )
        counts = {'all': 0}
        for row_purpose, row_type, count in await db.execute(counts_query):
            key = 'digest' if row_purpose == 'digest' else row_type or 'unassigned'
            counts[key] = counts.get(key, 0) + count
            counts['all'] += count
        if report_type:
            filters.append(
                Template.purpose == 'digest'
                if report_type == 'digest'
                else and_(Template.purpose == 'research', Template.report_type == report_type)
            )
        total = await db.scalar(select(func.count()).select_from(Template).where(*filters))
        query = (
            select(Template)
            .options(defer(Template.prompt), defer(Template.screening_prompt), defer(Template.screening_categories))
            .where(*filters)
            .order_by(Template.updated_at.desc(), Template.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(await db.scalars(query)), total, counts
