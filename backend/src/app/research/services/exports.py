"""统一图片/导出资源；持久化队列与独立重试，不另建导出表。"""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

from sqlalchemy import select

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.research.models.research_models import PipelineReportAsset, utcnow
from app.research.repositories.research_repository import ResearchDao
from app.research.services.export_storage import ReportExportStorage
from app.research.services.exporters import build_file
from app.research.services.model_generation import ModelGateway
from app.research.services.reports import ResearchReportService
from config.database import AsyncSessionLocal
from exceptions.exception import ServiceException


class ResearchReportExportService:
    MAX_ATTEMPTS = 3
    _media_types = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pdf': 'application/pdf',
        'png': 'image/png',
    }

    @classmethod
    def _extension(cls, mime):
        for ext, value in cls._media_types.items():
            if mime == value:
                return ext
        raise ServiceException(message='不支持的资源类型')

    @classmethod
    def _record_dict(cls, row):
        ext = cls._extension(row.mime_type)
        return {
            'id': wire_id(row.id),
            'exportId': wire_id(row.id),
            'reportId': wire_id(row.report_id),
            'taskId': wire_id(row.task_id),
            'type': row.type,
            'format': ext,
            'status': row.status,
            'contentType': row.mime_type,
            'reportVersionNo': row.config_snapshot.get('version'),
            'errorMessage': row.error or '',
            'createdAt': format_business_time(row.created_at),
            'downloadUrl': f'/pipeline/research/assets/{row.id}/download' if row.status == 'completed' else '',
        }

    @classmethod
    async def create(cls, db, *, user_id, report_id, file_format, allow_draft=False):
        if file_format not in {'docx', 'pdf'}:
            raise ServiceException(message='仅支持 DOCX/PDF 导出')
        report, _ = await ResearchReportService._get_export_report(db, user_id, report_id, allow_draft=allow_draft)
        row = PipelineReportAsset(
            report_id=report.id,
            type='export',
            mime_type=cls._media_types[file_format],
            status='queued',
            config_snapshot={'version': report.version, 'report': ResearchReportService.export_snapshot(report)},
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        await ResearchDao.add_report_export(db, row)
        await db.commit()
        return cls._record_dict(row)

    @classmethod
    async def list(cls, db, *, user_id, report_id, include_all=False):
        await ResearchReportService._owned(db, user_id, report_id, include_all=include_all)
        rows = await ResearchDao.list_assets(db, report_id, 'export')
        return {'rows': [cls._record_dict(row) for row in rows], 'total': len(rows)}

    @classmethod
    async def queue_images(cls, db, job, report):
        config = job.config_snapshot['template'].get('image_config') or {}
        if not config.get('enabled'):
            return
        model = job.config_snapshot.get('image_model')
        if not model:
            raise ServiceException(message='图片模型未配置')
        count = int(config.get('count', 1))
        if not 1 <= count <= 10:
            raise ServiceException(message='配图数量须在 1 至 10 之间')
        for index in range(count):
            row = PipelineReportAsset(
                report_id=report.id,
                task_id=job.id,
                type='image',
                mime_type='image/png',
                prompt=str(config.get('prompt') or report.title),
                model_id=parse_business_id(model['id']),
                config_snapshot={'model': deepcopy(model), 'image_config': deepcopy(config)},
                position=str(index + 1),
                status='queued',
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            await ResearchDao.add_report_export(db, row)

    @classmethod
    async def process(cls, export_id, worker_id='asset-worker'):
        export_id = parse_business_id(export_id)
        # 资源表没有租约列。使用行锁跨外部调用：进程退出回滚 queued；
        # 锁竞争 SKIP LOCKED；按稳定资源 ID 寻找落盘文件避免重复收费。
        async with AsyncSessionLocal() as db:
            row = await db.scalar(
                select(PipelineReportAsset)
                .where(PipelineReportAsset.id == export_id, PipelineReportAsset.status == 'queued')
                .with_for_update(skip_locked=True)
            )
            if not row:
                return
            ext = cls._extension(row.mime_type)
            key = ReportExportStorage.build_key(
                row.id, ext, row.created_at.year, row.created_at.month, row.created_at.day
            )
            row.status = 'running'
            try:
                try:
                    content = await asyncio.to_thread(ReportExportStorage.read, key)
                except FileNotFoundError:
                    if row.type == 'image':
                        content = await ModelGateway.call(
                            db,
                            row.config_snapshot['model'],
                            capability='image_generate',
                            prompt=row.prompt,
                            request_id=row.id,
                            task_id=row.task_id,
                        )
                    else:
                        _, mime, content = await asyncio.to_thread(
                            build_file, SimpleNamespace(**row.config_snapshot['report']), ext, is_draft=False
                        )
                        if mime != row.mime_type:
                            raise ValueError('MIME mismatch')
                    await asyncio.to_thread(ReportExportStorage.write, key, content)
                row.storage_key = key
                row.status, row.error = 'completed', None
            except asyncio.CancelledError:
                raise
            except Exception:
                row.status, row.error = 'failed', '资源生成失败；请检查模型配置后明确重试'
            row.updated_at = utcnow()
            await db.commit()

    @classmethod
    async def retry(cls, db, user_id, asset_id):
        row = await ResearchDao.get_asset(db, asset_id, user_id, lock=True)
        if not row:
            raise ServiceException(message='资源不存在或无权访问')
        if row.status == 'completed':
            return cls._record_dict(row)
        if row.status != 'failed':
            raise ServiceException(message='仅失败资源可重试')
        if row.type == 'image':
            model_id = (row.config_snapshot.get('model') or {}).get('id')
            model = await ResearchDao.get_model(db, model_id) if model_id is not None else None
            if not model or not model.is_enabled or 'image_generate' not in (model.capabilities or []):
                raise ServiceException(message='配图需配置启用且具备 image_generate 能力的模型')
            if model.provider not in ModelGateway.supported_providers:
                raise ServiceException(message='图片模型原生协议不受支持，请明确配置 compatible 端点')
        row.status, row.error = 'queued', None
        await db.commit()
        return cls._record_dict(row)

    @classmethod
    async def download(cls, db, *, user_id, export_id):
        row = await ResearchDao.get_asset(db, export_id, user_id)
        if not row or row.status != 'completed' or not row.storage_key:
            raise ServiceException(message='资源不存在、尚未完成或无权访问')
        try:
            content = await asyncio.to_thread(ReportExportStorage.read, row.storage_key)
        except OSError:
            raise ServiceException(message='资源文件已失效') from None
        return f'{row.id}.{cls._extension(row.mime_type)}', row.mime_type, content
