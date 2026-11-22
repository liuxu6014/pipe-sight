"""规范任务入队与取消；选材在入队事务冻结，重试复用快照。"""

import json
from copy import deepcopy
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.business_ids import generation_request_data, generation_request_fingerprint, parse_business_id, wire_id
from app.intelligence.services.templates import PipelineTemplateService
from app.research.models.research_models import PipelineReport, PipelineResearchJob, utcnow
from app.research.repositories.research_repository import ResearchDao
from app.research.services.digest_rules import screening_rule_snapshot
from app.research.services.digest_screening import DigestScreeningService
from app.research.services.evidence import ResearchEvidenceService
from app.research.services.project_demand_document import PROJECT_DEMAND_FORMAT, PROJECT_DEMAND_TEMPLATE_NAMES
from app.research.services.report_labels import display_template_prompt
from exceptions.exception import ServiceException


def report_type(value) -> str:
    return {'project-demand': 'research', 'research-demand': 'research', 'technology-route': 'research'}.get(
        value, value
    )


def payload_data(payload) -> dict:
    return generation_request_data(payload)


class ResearchJobService:
    @staticmethod
    def _validate_options(options) -> None:
        if options.get('publicSupplement'):
            raise ServiceException(message='公开补充尚未开放，请选择真实资料')
        if options.get('language') not in {None, 'zh'}:
            raise ServiceException(message='当前只支持简体中文')

    @staticmethod
    def _validate_digest_materials(kind, materials) -> None:
        if kind in {'weekly', 'monthly'} and any(item.get('type') == 'file' for item in materials):
            raise ServiceException(message='周报、月报不支持上传资料，请选择采集内容')

    @staticmethod
    async def _resolve_digest_candidates(db, data, kind) -> list[dict]:
        """周报/月报未提交复筛结果时，按报告周期自动圈定候选资讯，后台再复筛。"""
        from datetime import date  # noqa: PLC0415

        from app.intelligence.schemas.pipeline import PipelineDigestScreeningModel  # noqa: PLC0415
        from app.research.digest_policy import DIGEST_SELECTION_LIMIT  # noqa: PLC0415

        period = data.get('period') or []
        if len(period) != 2:
            raise ServiceException(message='周报和月报需要完整的报告周期')
        try:
            scope = PipelineDigestScreeningModel(
                period=[date.fromisoformat(str(value)[:10]) for value in period],
                report_type=kind,
                template_id=data.get('template_id'),
            )
        except (TypeError, ValueError) as exc:
            raise ServiceException(message='报告周期格式无效') from exc
        candidates, total = await ResearchDao.search_digest_candidates(db, scope, all_candidates=True)
        if not total:
            raise ServiceException(message='报告周期内没有符合范围的资讯，请调整周期')
        limit = int((data.get('options') or {}).get('itemCount') or 10)
        if not 1 <= limit <= DIGEST_SELECTION_LIMIT:
            limit = DIGEST_SELECTION_LIMIT
        return [{'type': 'article', 'id': wire_id(row.id)} for row in candidates[:limit]]

    @staticmethod
    def queued_stage_rows(stage_labels) -> list[dict]:
        return [{'key': key, 'label': label, 'status': 'waiting', 'progress': 0} for key, label in stage_labels]

    @staticmethod
    async def _reused(db, existing, user_id, fingerprint, serializer) -> dict:
        report = await ResearchDao.get_report(db, existing.report_id, user_id)
        snapshot = existing.config_snapshot
        expected = snapshot.get('request_fingerprint')
        stored_request = snapshot.get('request') or {}
        image_config = (snapshot.get('template') or {}).get('image_config') or {}
        if stored_request.get('diagram') is False and image_config.get('enabled') is True:
            # 旧快照把省略补成 false，但实际继承了开启配置。按实际执行语义
            # 识别为继承，既保留原请求重放，也拒绝显式关闭复用开启任务。
            inherited_request = {key: value for key, value in stored_request.items() if key != 'diagram'}
            expected = generation_request_fingerprint(inherited_request, existing.materials)
        if not report or expected != fingerprint:
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
        screening_cache=None,
    ) -> dict:
        data = payload_data(payload)
        for field in ('template_id', 'report_id'):
            if data.get(field) is not None:
                data[field] = wire_id(data[field])
        if schedule_id is not None:
            schedule_id = parse_business_id(schedule_id)
        cls._validate_options(data.get('options') or {})
        selections = data.get('materials') or data.get('selected_item_ids') or []
        screening_id = data.get('screening_id')
        kind = report_type(data.get('report_type', data.get('type')))
        if kind not in {'article', 'research', 'daily', 'weekly', 'monthly'}:
            raise ServiceException(message='成果类型不合法')
        structured_digest = kind in {'weekly', 'monthly'}
        if screening_id and selections:
            raise ServiceException(message='简报资料由系统筛选结果确定，无需提交资料编号')
        if not screening_id and structured_digest and not selections:
            selections = await cls._resolve_digest_candidates(db, data, kind)
        if not screening_id and not 1 <= len(selections) <= 50:  # noqa: PLR2004
            raise ServiceException(message='请选择 1 至 50 条资料，超限不会截断')
        title = str(data.get('title') or '').strip()
        if not title:
            raise ServiceException(message='成果标题不能为空')
        clean_request = {k: v for k, v in data.items() if k not in {'request_id', 'requestId'}}
        request_id = str(data.get('request_id') or f'manual:{uuid4()}')
        if schedule_id is None and not request_id.startswith('manual:'):
            request_id = 'manual:' + request_id
        if len(request_id) > 128:  # noqa: PLR2004
            raise ServiceException(message='幂等键超过 128 字符')
        existing = await ResearchDao.get_research_job_by_request_id(db, request_id)
        if existing:
            fingerprint = generation_request_fingerprint(clean_request, existing.materials)
            return await cls._reused(db, existing, user_id, fingerprint, job_serializer)
        purpose = 'digest' if kind in {'daily', 'weekly', 'monthly'} else kind
        if structured_digest:
            template = await template_service.get_digest_for_run(db, kind, user_id, data.get('template_id'))
        else:
            template = await template_service.get_published(db, data.get('template_id'), user_id)
            if not template:
                raise ServiceException(message='请选择已启用的模板')
            if template.purpose != purpose:
                raise ServiceException(message='模板用途与成果类型不匹配')
        requested_type = data.get('report_type')
        if (
            purpose == 'research'
            and requested_type in {'research-demand', 'technology-route', 'project-demand'}
            and getattr(template, 'report_type', None) != requested_type
        ):
            raise ServiceException(message='模板尚未绑定当前报告类型，请选择该类型下的模板')
        if purpose == 'digest' and not structured_digest:
            PipelineTemplateService.validate_digest_cadence(template, kind)
        image_config = PipelineTemplateService.effective_image_config(template.image_config, data)
        model_id, image_model_id = await PipelineTemplateService.generation_model_ids(
            db, purpose, template, image_config, required=True
        )
        model = await template_service.validate_models(db, model_id, image_model_id, image_config)
        image_model = None
        if image_config.get('enabled'):
            image_model = await ResearchDao.get_model(db, image_model_id)
            if not 1 <= int(image_config.get('count', 1)) <= 10:  # noqa: PLR2004
                raise ServiceException(message='配图数量须在 1 至 10 之间')
        screened = {}
        if screening_id:
            if not structured_digest:
                raise ServiceException(message='只有周报和月报可以使用简报复筛结果')
            materials, screened = await DigestScreeningService.approved(
                db, screening_cache, user_id, data, template, model
            )
        else:
            materials = await ResearchEvidenceService.resolve(db, user_id, selections, payload)
        cls._validate_digest_materials(kind, materials)
        fingerprint = generation_request_fingerprint(clean_request, materials)
        params = deepcopy(model.parameters or {})
        budget = int(params.get('context_chars', 100000))
        prompt = display_template_prompt(template.name, template.prompt)
        if (
            sum(len(i['content']) + len(i['title']) for i in materials)
            + len(prompt)
            + len(json.dumps(clean_request, ensure_ascii=False, default=str))
            > budget
        ):
            if screening_id:
                raise ServiceException(message='通过筛选的文章正文超过模型容量，请收紧筛选提示词后重新筛选')
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
                'report_type': getattr(template, 'report_type', None),
                'digestCadence': PipelineTemplateService.digest_cadence(template),
                'sections': deepcopy(template.sections),
                'image_config': image_config,
                'image_model_id': wire_id(image_model_id),
            },
            'model': {
                'id': wire_id(model.id),
                'provider': model.provider,
                'code': model.code,
                'base_url': model.base_url,
                'parameters': params,
            },
        }
        if structured_digest:
            snapshot['document_format'] = 'digest-reference-v1'
            snapshot['fixed_digest_format'] = PipelineTemplateService.is_fixed_digest(template)
            snapshot['digest_screening'] = screened or screening_rule_snapshot(
                template,
                general_prompt=data.get('screening_prompt'),
                categories=data.get('screening_categories'),
            )
            for field in ('outline', 'template_prompt', 'templatePrompt', 'template_version'):
                snapshot['request'].pop(field, None)
        elif (
            getattr(template, 'report_type', None) == 'project-demand'
            and template.name in PROJECT_DEMAND_TEMPLATE_NAMES
        ):
            snapshot['document_format'] = PROJECT_DEMAND_FORMAT
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
    async def retry(cls, db, *, user_id, job_id, stage_labels, job_serializer) -> dict:
        job = await ResearchDao.get_research_job(db, job_id, user_id, lock=True)
        if not job or job.status not in {'failed', 'cancelled'}:
            raise ServiceException(message='只能重试失败或取消的任务')
        # One failed attempt has one successor. The parent row lock serializes
        # retries from stale pages/tabs, and the request key survives refreshes
        # and lost responses. Retry a failed successor to create another attempt.
        request_id = f'retry:{wire_id(job.id)}'
        existing = await ResearchDao.get_research_job_by_request_id(db, request_id)
        if existing:
            report = await ResearchDao.get_report(db, existing.report_id, user_id)
            if not report or existing.report_id != job.report_id:
                raise ServiceException(message='重试任务记录不一致，请联系管理员')
            return {**job_serializer(existing, report=report), 'reused': True}
        # 按原任务冻结的模型选择复核，不改用当前模板或生成无效的新尝试。
        snapshot = job.config_snapshot or {}
        cls._validate_digest_materials(snapshot.get('type'), job.materials or [])
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
            request_id=request_id,
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
        if new.config_snapshot.get('digest_screening') and 'labels' not in new.config_snapshot['digest_screening']:
            new.config_snapshot['digest_screening'].pop('retained_ids', None)
        await ResearchDao.add_research_job(db, new)
        await db.commit()
        return {**job_serializer(new, report=report), 'reused': False}

    @staticmethod
    async def cancel(db, *, user_id, job_id, job_serializer) -> dict:
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
