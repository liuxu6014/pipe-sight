"""初始化真实公开来源并执行一次采集。

运行方式（容器内）：python scripts/bootstrap_real_pipeline.py
"""

import asyncio

from sqlalchemy import select

from config.database import AsyncSessionLocal
# Import referenced ORM tables so SQLAlchemy can resolve the pipeline foreign keys
# when this standalone script flushes objects outside the application bootstrap.
from module_admin.entity.do import job_do, user_do  # noqa: F401
from module_pipeline.service.pipeline_collection_service import PipelineCollectionService
from module_pipeline.entity.do.pipeline_do import PipelineSource


async def main() -> None:
    if AsyncSessionLocal is None:
        raise RuntimeError('数据库会话未初始化')
    async with AsyncSessionLocal() as db:
        sources = await PipelineCollectionService.ensure_real_sources(db)
        source_ids = [item.source_id for item in sources]
        await db.commit()
        # async_sessionmaker uses SQLAlchemy's default expire-on-commit behavior;
        # reload the rows before the first collector reads their attributes.
        sources = (
            await db.execute(select(PipelineSource).where(PipelineSource.source_id.in_(source_ids)))
        ).scalars().all()
        for source_id in source_ids:
            source = (
                await db.execute(select(PipelineSource).where(PipelineSource.source_id == source_id))
            ).scalars().one()
            result = await PipelineCollectionService.collect_source(db, source)
            print(result)


if __name__ == '__main__':
    asyncio.run(main())
