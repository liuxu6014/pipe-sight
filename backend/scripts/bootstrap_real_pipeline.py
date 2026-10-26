"""初始化真实公开来源并按来源执行一次采集。

运行方式（容器内）：python scripts/bootstrap_real_pipeline.py
如需显式重新激活已停用来源：python scripts/bootstrap_real_pipeline.py --reactivate
"""

import argparse
import asyncio

from sqlalchemy import select

# Import referenced ORM tables so SQLAlchemy can resolve the pipeline foreign keys
# when this standalone script flushes objects outside the application bootstrap.
import app.infrastructure.models.jobs
import app.system.models.user  # noqa: F401
from app.intelligence.models.pipeline_models import PipelineSource
from app.intelligence.services.collection import PipelineCollectionService
from config.database import AsyncSessionLocal


async def main(*, reactivate: bool = False) -> None:
    if AsyncSessionLocal is None:
        raise RuntimeError('数据库会话未初始化')
    async with AsyncSessionLocal() as db:
        sources = await PipelineCollectionService.ensure_real_sources(db, reactivate_existing=reactivate)
        source_ids = [item.source_id for item in sources]
        await db.commit()
        failures: list[str] = []
        for source_id in source_ids:
            source = (
                await db.execute(select(PipelineSource).where(PipelineSource.source_id == source_id))
            ).scalars().one()
            try:
                result = await PipelineCollectionService.collect_source(db, source)
            except Exception as exc:
                failures.append(source_id)
                print({'source_id': source_id, 'status': 'failed', 'error': str(exc)[:500]})
            else:
                print(result)
        if failures:
            raise RuntimeError(f'以下数据源采集失败，请查看逐源错误后处理：{", ".join(failures)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='初始化真实公开来源并执行一次采集')
    parser.add_argument(
        '--reactivate',
        action='store_true',
        help='显式重新激活已有但被管理员停用的内置来源；默认保留管理员当前状态',
    )
    args = parser.parse_args()
    asyncio.run(main(reactivate=args.reactivate))
