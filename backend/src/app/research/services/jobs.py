"""规范任务入队与取消；选材在入队事务冻结，重试复用快照。"""

import json
from copy import deepcopy
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.business_ids import generation_request_fingerprint, parse_business_id, wire_id
from app.intelligence.services.templates import PipelineTemplateService
from app.research.models.research_models import PipelineReport, PipelineResearchJob, utcnow
from app.research.repositories.research_repository import ResearchDao
from app.research.services.evidence import ResearchEvidenceService
from exceptions.exception import ServiceException


def report_type(value):
    return {'project-demand': 'research', 'research-demand': 'research', 'technology-route': 'research'}.get(
        value, value
    )


def payload_data(payload):
    return payload.model_dump(by_alias=False) if hasattr(payload, 'model_dump') else dict(payload)


class ResearchJobService:
    @staticmethod
    def _validate_options(options):
        if options.get('publicSupplement'):
            raise ServiceException(message='公开补充尚未开放，请选择真实资料')
        if options.get('language') not in {None, 'zh'}:
            raise ServiceException(message='当前只支持简体中文')

    @staticmethod
    def queued_stage_rows(stage_labels):
        return [{'key': key, 'label': label, 'status': 'waiting', 'progress': 0} for key, label in stage_labels]

    @staticmethod
    async def _reused(db, existing, user_id, fingerprint, serializer):
        report = await ResearchDao.get_report(db, existing.report_id, user_id)
        if not report or existing.config_snapshot.get('request_fingerprint') != fingerprint:
            raise ServiceException(message='幂等键已被其他请求使用')
        return {**serializer(existing, report=report), 'reused': True}

    @classmethod
    async def queue(
        cls,
        db,
        *,
        user_id,
        owner_name,
        payload,
        stage_labels,
        job_serializer,
        template_service,
        schedule_id=None,
        commit=True,
    ):
        data = payload_data(payload)
        for field in ('template_id', 'report_id'):
            if data.get(field) is not None:
                data[field] = wire_id(data[field])
        if schedule_id is not None:
            schedule_id = parse_business_id(schedule_id)
        cls._validate_options(data.get('options') or {})
        selections = data.get('materials') or data.get('selected_item_ids') or []
        if not 1 <= len(selections) <= 50:
            raise ServiceException(message='请选择 1 至 50 条资料，超限不会截断')
        kind = report_type(data.get('report_type', data.get('type')))
        if kind not in {'article', 'research', 'daily', 'weekly', 'monthly'}:
            raise ServiceException(message='成果类型不合法')
        title = str(data.get('title') or '').strip()
        if not title:
            raise ServiceException(message='成果标题不能为空')
        clean_request = {k: v for k, v in data.items() if k not in {'request_id', 'requestId'}}
        request_id = str(data.get('request_id') or f'manual:{uuid4()}')
        if schedule_id is None and not request_id.startswith('manual:'):
            request_id = 'manual:' + request_id
        if len(request_id) > 128:
            raise ServiceException(message='幂等键超过 128 字符')
        existing = await ResearchDao.get_research_job_by_request_id(db, request_id)
        if existing:
            fingerprint = generation_request_fingerprint(clean_request, existing.materials)
            return await cls._reused(db, existing, user_id, fingerprint, job_serializer)
        template = await template_service.get_published(db, data.get('template_id'))
        if not template:
            raise ServiceException(message='请选择已启用的模板')
        purpose = 'digest' if kind in {'daily', 'weekly', 'monthly'} else kind
        if template.purpose != purpose:
            raise ServiceException(message='模板用途与成果类型不匹配')
        model = await template_service.validate_models(
            db, template.model_id, template.image_model_id, template.image_config
        )
        image_config = deepcopy(template.image_config or {})
        if data.get('diagram') or (data.get('options') or {}).get('generateImages'):
            image_config['enabled'] = True
        image_model = None
        if image_config.get('enabled'):
            await template_service.validate_models(db, template.model_id, template.image_model_id, image_config)
            image_model = await ResearchDao.get_model(db, template.image_model_id)
            if not 1 <= int(image_config.get('count', 1)) <= 10:
                raise ServiceException(message='配图数量须在 1 至 10 之间')
        materials = await ResearchEvidenceService.resolve(db, user_id, selections, payload)
        fingerprint = generation_request_fingerprint(clean_request, materials)
        params = deepcopy(model.parameters or {})
        budget = int(params.get('context_chars', 100000))
        prompt = template.prompt
        if (
            sum(len(i['content']) + len(i['title']) for i in materials)
            + len(prompt)
            + len(json.dumps(clean_request, ensure_ascii=False, default=str))
            > budget
        ):
            raise ServiceException(message='所选正文超过模型上下文预算，请减少资料或分批提炼')
        now = utcnow()
        existing_report_id = data.get('report_id')
        report = (
            await ResearchDao.get_report(db, existing_report_id, user_id, lock=True) if existing_report_id else None
        )
        if existing_report_id and not report:
            raise ServiceException(message='成果不存在或无权访问')
        if report is not None and report.type != kind:
            raise ServiceException(message='重新生成不能改变成果类型')
        if schedule_id:
            schedule = await ResearchDao.lock_digest_schedule_for_update(db, schedule_id, user_id)
            if not schedule or schedule.template_id != template.id:
                raise ServiceException(message='自动计划与成果所有者或模板不匹配')
        if report is None:
            report = PipelineReport(
                user_id=user_id,
                title=title,
                type=kind,
                template_id=template.id,
                content='',
                version=1,
                created_at=now,
                updated_at=now,
            )
            await ResearchDao.add_report(db, report)
        snapshot = {
            'request_fingerprint': fingerprint,
            'request': deepcopy(clean_request),
            'title': title,
            'type': kind,
            'report_start_version': report.version,
            'template': {
                'id': wire_id(template.id),
                'name': template.name,
                'prompt': prompt,
                'purpose': template.purpose,
                'sections': deepcopy(template.sections),
                'image_config': image_config,
                'image_model_id': wire_id(template.image_model_id),
            },
            'model': {
                'id': wire_id(model.id),
                'provider': model.provider,
                'code': model.code,
                'base_url': model.base_url,
                'parameters': params,
            },
        }
        # 请求只含 ID/筛选；绝不从前端接受正文副本或凭证。
        snapshot['request'].pop('materials', None)
        snapshot['request']['selected_item_ids'] = [{'type': item['type'], 'id': item['id']} for item in materials]
        if image_model is not None:
            snapshot['image_model'] = {
                'id': wire_id(image_model.id),
                'provider': image_model.provider,
                'code': image_model.code,
                'base_url': image_model.base_url,
                'parameters': deepcopy(image_model.parameters or {}),
            }
            snapshot['image_model']['parameters'].update(
                {key: image_config[key] for key in ('size', 'quality', 'style') if key in image_config}
            )
        job = PipelineResearchJob(
            report_id=report.id,
            schedule_id=schedule_id,
            request_id=request_id,
            status='queued',
            progress=0,
            config_snapshot=snapshot,
            materials=materials,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        try:
            await ResearchDao.add_research_job(db, job)
            if commit:
                await db.commit()
        except IntegrityError:
            if not commit:
                raise
            await db.rollback()
            existing = await ResearchDao.get_research_job_by_request_id(db, request_id)
            if existing and commit:
                fingerprint = generation_request_fingerprint(clean_request, existing.materials)
                return await cls._reused(db, existing, user_id, fingerprint, job_serializer)
            raise
        return {**job_serializer(job, report=report), 'reused': False}

    @classmethod
    async def retry(cls, db, *, user_id, job_id, stage_labels, job_serializer):
        job = await ResearchDao.get_research_job(db, job_id, user_id, lock=True)
        if not job or job.status not in {'failed', 'cancelled'}:
            raise ServiceException(message='只能重试失败或取消的任务')
        # 按原任务冻结的模型选择复核，不改用当前模板或生成无效的新尝试。
        snapshot = job.config_snapshot or {}
        await PipelineTemplateService.validate_models(
            db,
            (snapshot.get('model') or {}).get('id'),
            (snapshot.get('image_model') or {}).get('id'),
            (snapshot.get('template') or {}).get('image_config'),
        )
        # 明确重跑创建新尝试，旧终态/结果不覆盖。
        new = PipelineResearchJob(
            report_id=job.report_id,
            schedule_id=job.schedule_id,
            request_id=f'manual:{uuid4()}',
            status='queued',
            progress=0,
            attempts=0,
            config_snapshot=deepcopy(job.config_snapshot),
            materials=deepcopy(job.materials),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        report = await ResearchDao.get_report(db, job.report_id, user_id, lock=True)
        new.config_snapshot['report_start_version'] = report.version
        await ResearchDao.add_research_job(db, new)
        await db.commit()
        return job_serializer(new, report=report)

    @staticmethod
    async def cancel(db, *, user_id, job_id, job_serializer):
        job = await ResearchDao.get_research_job(db, job_id, user_id, lock=True)
        if not job:
            raise ServiceException(message='任务不存在或无权访问')
        if job.status in {'completed', 'failed'}:
            raise ServiceException(message='任务已结束')
        job.status, job.finished_at = 'cancelled', utcnow()
        job.execution_token = job.lease_expires_at = None
        report = await ResearchDao.get_report(db, job.report_id, user_id)
        await db.commit()
        return job_serializer(job, report=report)
