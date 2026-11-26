"""持久解析队列；安全扫描后才 ready，CAS 防止过期解析回写。"""

import asyncio
from datetime import timedelta

from sqlalchemy import update

from app.library.models.materials import PipelineMaterial, utcnow
from app.library.repositories.classification_repository import INTERRUPTED_MESSAGE, MaterialClassificationDao
from app.library.repositories.material_repository import MaterialDao
from app.library.services.classification import ClassificationSuperseded, MaterialClassificationService
from app.library.services.materials import MaterialFileService
from app.system.services.file_scan import FileScanService
from config.database import AsyncSessionLocal

_material_tasks = {}
_classification_tasks = {}
MAX_ATTEMPTS = 3


async def process_material_parse(material_id, worker_id='material-worker') -> None:
    async with AsyncSessionLocal() as db:
        row = await MaterialDao.claim_material_parse(db, material_id)
        if not row:
            return
        token, path, name = row._parse_token, MaterialFileService.safe_local_path(row.storage_key), row.filename
    title = None
    try:
        status, message, text, _ = await asyncio.to_thread(
            MaterialFileService.parse, str(path) if path else None, name, requested_at=utcnow().isoformat()
        )
        error = None if status == 'ready' else message
        if status == 'queued':
            status, error = 'failed', '此文件类型尚未配置解析器'
        elif status == 'ready' and text:
            # 解析成功后尝试用 AI 提取标题自动命名；失败保留原文件名。
            try:
                async with AsyncSessionLocal() as db:
                    title = await MaterialClassificationService.extract_title(
                        db,
                        content=text,
                        request_id=f'material-title:{material_id}:{token}',
                    )
            except Exception:
                title = None
    except asyncio.CancelledError:
        raise
    except Exception:
        status, error, text = 'failed', '资料解析失败，请检查原文件后重试', None
    async with AsyncSessionLocal() as db:
        await MaterialDao.finish_material_parse(
            db, material_id, parse_token=token, status=status, extracted_text=text, error=error, name=title
        )


async def recover_material_parses() -> dict:
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
    await recover_material_classifications()
    return {'found': len(ids), 'dispatched': dispatched}


async def process_material_classification(material_id) -> None:
    async with AsyncSessionLocal() as db:
        claim = await MaterialClassificationDao.claim(db, material_id)
    if not claim:
        return
    token, row = claim
    status, category_id, error = 'failed', None, None
    cancelled = False

    async def current_before_call() -> bool:
        async with AsyncSessionLocal() as check_db:
            return await MaterialClassificationDao.is_current(check_db, material_id, token=token, version=row.version)

    try:
        path = MaterialFileService.safe_local_path(row.storage_key)
        scan = await asyncio.to_thread(FileScanService.scan, str(path) if path else None, row.filename)
        if scan.status != 'clean':
            error = '资料未通过安全扫描，暂不可分类'
        elif not await current_before_call():
            raise ClassificationSuperseded
        else:
            async with AsyncSessionLocal() as db:
                try:
                    status, category_id, error = await MaterialClassificationService.classify(
                        db,
                        title=row.name,
                        content=row.edited_text if row.edited_text is not None else row.extracted_text or '',
                        request_id=f'material-classification:{row.id}:{token}',
                        before_call=current_before_call,
                    )
                except Exception:
                    # Model audit writes are kept; raw provider errors never reach the UI.
                    await db.commit()
                    raise
    except ClassificationSuperseded:
        status, error = 'completed', None
    except asyncio.CancelledError:
        cancelled, error = True, INTERRUPTED_MESSAGE
    except Exception as exc:
        error = getattr(exc, 'message', None) or '资料分类失败，请检查内容处理模型和类别规则后手动重试'
        error = error[:240]
    async with AsyncSessionLocal() as db:
        await MaterialClassificationDao.finish(
            db,
            material_id,
            token=token,
            status=status,
            category_id=category_id,
            error=error,
            expected_version=row.version,
        )
    if cancelled:
        raise asyncio.CancelledError


async def recover_material_classifications() -> None:
    async with AsyncSessionLocal() as db:
        ids = await MaterialClassificationDao.ready(db)
    for identity in ids:
        if identity in _classification_tasks:
            continue
        task = asyncio.create_task(process_material_classification(identity))
        _classification_tasks[identity] = task
        task.add_done_callback(lambda _, key=identity: _classification_tasks.pop(key, None))


async def stop_material_parse_tasks() -> None:
    tasks = [*list(_material_tasks.values()), *list(_classification_tasks.values())]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _material_tasks.clear()
    _classification_tasks.clear()
