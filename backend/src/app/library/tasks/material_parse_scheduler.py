"""持久解析队列；安全扫描后才 ready，CAS 防止过期解析回写。"""

import asyncio
from datetime import timedelta

from sqlalchemy import update

from app.library.models.materials import PipelineMaterial, utcnow
from app.library.repositories.material_repository import MaterialDao
from app.library.services.materials import MaterialFileService
from app.system.services.file_scan import FileScanService
from config.database import AsyncSessionLocal

_material_tasks = {}
MAX_ATTEMPTS = 3


async def process_material_parse(material_id, worker_id='material-worker'):
    async with AsyncSessionLocal() as db:
        row = await MaterialDao.claim_material_parse(db, material_id)
        if not row:
            return
        token, path, name = row._parse_token, MaterialFileService.safe_local_path(row.storage_key), row.filename
    try:
        scan = await asyncio.to_thread(FileScanService.scan, str(path) if path else None, name)
        if scan.status != 'clean':
            status, error, text = 'failed', '资料未通过安全扫描，暂不可使用', None
        else:
            status, message, text, _ = await asyncio.to_thread(
                MaterialFileService.parse, str(path) if path else None, name, requested_at=utcnow().isoformat()
            )
            error = None if status == 'ready' else message
            if status == 'queued':
                status, error = 'failed', '此文件类型尚未配置解析器'
    except asyncio.CancelledError:
        raise
    except Exception:
        status, error, text = 'failed', '资料解析失败，请检查原文件后重试', None
    async with AsyncSessionLocal() as db:
        await MaterialDao.finish_material_parse(
            db, material_id, parse_token=token, status=status, extracted_text=text, error=error
        )


async def recover_material_parses():
    if AsyncSessionLocal is None:
        return {'found': 0, 'dispatched': 0}
    async with AsyncSessionLocal() as db:
        # 解析不调用付费模型；过期更新先隔离旧令牌再允许重试。
        await db.execute(
            update(PipelineMaterial)
            .where(PipelineMaterial.status == 'parsing', PipelineMaterial.updated_at < utcnow() - timedelta(minutes=15))
            .values(status='queued', updated_at=utcnow())
        )
        await db.commit()
        ids = await MaterialDao.list_material_ids_for_dispatch(db)
    dispatched = 0
    for item_id in ids:
        if item_id in _material_tasks:
            continue
        task = asyncio.create_task(process_material_parse(item_id))
        _material_tasks[item_id] = task
        task.add_done_callback(lambda _, key=item_id: _material_tasks.pop(key, None))
        dispatched += 1
    return {'found': len(ids), 'dispatched': dispatched}


async def stop_material_parse_tasks():
    tasks = list(_material_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _material_tasks.clear()
