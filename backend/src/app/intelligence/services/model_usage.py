"""模型路由每日调用额度。"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert

from app.intelligence.models.configuration import PipelineModelRouteUsage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PipelineModelUsageService:
    """使用 PostgreSQL 原子 upsert 预占每日调用额度。"""

    @classmethod
    async def reserve(
        cls,
        db: AsyncSession,
        *,
        route_id: str,
        daily_limit: int,
        now: datetime | None = None,
    ) -> bool:
        if daily_limit <= 0:
            return True
        current = now or datetime.now()
        usage_date = datetime.combine(date(current.year, current.month, current.day), datetime.min.time())
        statement = insert(PipelineModelRouteUsage).values(
            route_id=route_id,
            usage_date=usage_date,
            call_count=1,
            create_time=current,
            update_time=current,
        ).on_conflict_do_update(
            index_elements=[PipelineModelRouteUsage.route_id, PipelineModelRouteUsage.usage_date],
            set_={
                'call_count': PipelineModelRouteUsage.call_count + 1,
                'update_time': current,
            },
            where=PipelineModelRouteUsage.call_count < daily_limit,
        )
        result = await db.execute(statement)
        return result.rowcount == 1


__all__ = ['PipelineModelUsageService']
