"""模板配置；旧发布接口只显式适配启停，不保留审批实体。"""

from copy import deepcopy
from typing import Any

from sqlalchemy import text

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.intelligence.models.configuration import PipelineTemplateVersion
from app.research.repositories.research_repository import ResearchDao
from app.research.services.model_generation import ModelGateway
from app.research.services.report_labels import display_template_name
from exceptions.exception import ServiceException


class PipelineTemplateService:
    @classmethod
    async def install_builtins(cls, db, *, user_id: int) -> dict:
        from app.intelligence.services.template_presets import builtin_templates  # noqa: PLC0415

        # Prevent duplicate installation in simultaneous tabs, without blocking other users.
        if db.get_bind().dialect.name == 'postgresql':
            await db.execute(
                text('SELECT pg_advisory_xact_lock(hashtext(:key))'), {'key': f'template-presets:{user_id}'}
            )
        rows = await ResearchDao.list_templates(db, user_id=user_id)
        existing = {(row.purpose, row.report_type, row.name) for row in rows}
        created = []
        for preset in builtin_templates():
            if (preset['purpose'], preset['report_type'], preset['name']) in existing:
                continue
            row = PipelineTemplateVersion(**deepcopy(preset), user_id=user_id)
            db.add(row)
            created.append(row)
        await db.commit()
        return {'created': len(created)}

    @staticmethod
    def digest_cadence(row) -> str | None:
        """旧表没有周期列：仅识别受控全名，不从用途或任意子串推断通用。"""
        if row.purpose != 'digest':
            return None
        names = {
            f'{prefix}{label}{suffix}': cadence
            for prefix in ('', '科技情报', '管网科技情报')
            for label, cadence in (('日报', 'daily'), ('周报', 'weekly'), ('月报', 'monthly'))
            for suffix in ('', '模板')
        }
        names.update({'通用简报': 'all', '通用简报模板': 'all', '检测技术专题周报': 'weekly'})
        return names.get(str(row.name or '').strip())

    @classmethod
    def validate_digest_cadence(cls, row, frequency) -> None:
        if cls.digest_cadence(row) not in {frequency, 'all'}:
            raise ServiceException(message='模板周期未知或与简报周期不匹配，请选择明确适用周期的模板')

    @staticmethod
    def effective_image_config(template_config, request) -> dict:
        config = deepcopy(template_config or {})
        options = request.get('options') or {}
        # 顶层显式选择优先；未提交才读取旧客户端选项，再回落模板默认。
        if 'diagram' in request:
            config['enabled'] = request['diagram']
        elif 'generateImages' in options:
            config['enabled'] = options['generateImages']
        return config

    @staticmethod
    def _dict(row) -> dict:
        return {
            'id': wire_id(row.id),
            'templateKey': wire_id(row.id),
            'name': display_template_name(row.name),
            'purpose': row.purpose,
            'category': row.purpose,
            'reportType': getattr(row, 'report_type', None),
            'digestCadence': PipelineTemplateService.digest_cadence(row),
            'description': row.description or '',
            'prompt': row.prompt,
            'modelId': wire_id(row.model_id),
            'imageModelId': wire_id(row.image_model_id),
            'sections': deepcopy(row.sections),
            'imageConfig': deepcopy(row.image_config),
            'isEnabled': row.is_enabled,
            'status': 'published' if row.is_enabled else 'retired',
            'formats': ['docx', 'pdf'],
            'updatedAt': format_business_time(row.updated_at),
        }

    @staticmethod
    async def ensure_default_templates(db) -> None:
        # 默认模板由迁移映射；运行时不自动创建模板或模型配置。
        return None

    @classmethod
    async def list_templates(cls, db, category=None, published_only=False, user_id=None) -> dict:
        purpose = {'project': 'research'}.get(category, category)
        rows = await ResearchDao.list_templates(db, purpose, user_id)
        rows = [row for row in rows if not published_only or row.is_enabled]
        result = []
        for row in rows:
            model_id, image_id = await cls.generation_model_ids(db, row.purpose, row, {'enabled': True})
            model = await ResearchDao.get_model(db, model_id) if model_id is not None else None
            image = await ResearchDao.get_model(db, image_id) if image_id is not None else None
            result.append(
                {
                    **cls._dict(row),
                    'modelId': wire_id(model_id),
                    'imageModelId': wire_id(image_id),
                    'modelConfigured': bool(
                        model
                        and model.is_enabled
                        and model.provider in ModelGateway.supported_providers
                        and 'text_generate' in (model.capabilities or [])
                    ),
                    'imageModelConfigured': bool(
                        image
                        and image.is_enabled
                        and image.provider in ModelGateway.supported_providers
                        and 'image_generate' in (image.capabilities or [])
                    ),
                }
            )
        return {'rows': result, 'total': len(rows)}

    @staticmethod
    async def get_published(db, template_key, user_id=None) -> PipelineTemplateVersion | None:
        if template_key is None:
            return None
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        return row if row and row.is_enabled else None

    @staticmethod
    async def generation_model_ids(db, purpose, template, image_config=None, *, required=False) -> tuple:
        from app.intelligence.services.translation_settings import (  # noqa: PLC0415
            GENERATION_PURPOSES,
            configured_model_id,
        )

        try:
            model_id = (
                await configured_model_id(db, GENERATION_PURPOSES[purpose][0])
                if purpose in {'research', 'digest'}
                else getattr(template, 'model_id', None)
            )
            image_id = (
                await configured_model_id(db, GENERATION_PURPOSES['image'][0])
                if (image_config or {}).get('enabled')
                else None
            )
        except ValueError as exc:
            raise ServiceException(message='模型用途配置无效，请联系管理员重新设置') from exc
        if required and model_id is None and purpose in {'research', 'digest'}:
            label = GENERATION_PURPOSES[purpose][1]
            raise ServiceException(message=f'请先在模型管理的用途配置中选择启用且具备 text_generate 能力的{label}')
        if required and (image_config or {}).get('enabled') and image_id is None:
            raise ServiceException(message='请先在模型管理的用途配置中选择启用且具备 image_generate 能力的图片生成模型')
        return model_id, image_id

    @staticmethod
    async def validate_models(db, model_id, image_model_id=None, image_config=None) -> Any:
        model = await ResearchDao.get_model(db, model_id) if model_id is not None else None
        if not model or not model.is_enabled or 'text_generate' not in (model.capabilities or []):
            raise ServiceException(message='请先配置启用且具备 text_generate 能力的正文模型')
        if model.provider not in ModelGateway.supported_providers:
            raise ServiceException(message='正文模型原生协议不受支持，请明确配置 compatible 端点')
        if (image_config or {}).get('enabled'):
            image = await ResearchDao.get_model(db, image_model_id) if image_model_id else None
            if not image or not image.is_enabled or 'image_generate' not in (image.capabilities or []):
                raise ServiceException(message='配图需配置启用且具备 image_generate 能力的模型')
            if image.provider not in ModelGateway.supported_providers:
                raise ServiceException(message='图片模型原生协议不受支持，请明确配置 compatible 端点')
        return model

    @classmethod
    async def save_draft(cls, db, *, template_key, payload, operator_id, operator_name, user_id) -> dict:
        purpose = payload.get('purpose') or {'project': 'research'}.get(
            payload.get('category'), payload.get('category')
        )
        if purpose not in {'article', 'research', 'digest'}:
            raise ServiceException(message='模板用途不合法')
        prompt = str(payload.get('prompt') or '').strip()
        name = str(payload.get('name') or '').strip()
        if not prompt or not name:
            raise ServiceException(message='模板名称和正文提示词必填')
        # BusinessId serializers also emit strings in model_dump(); ORM/asyncpg
        # must receive integers, without mutating the caller's payload.
        payload = dict(payload)
        for field in ('model_id', 'image_model_id'):
            if payload.get(field) is not None:
                payload[field] = parse_business_id(payload[field])
        if payload.get('model_id') is not None:
            await cls.validate_models(db, payload['model_id'])
        if payload.get('image_model_id') is not None:
            image = await ResearchDao.get_model(db, payload['image_model_id'])
            if not image or 'image_generate' not in (image.capabilities or []):
                raise ServiceException(message='图片模型须具备 image_generate 能力')
        selected_type = payload.get('report_type')
        if selected_type is not None and (
            purpose != 'research' or selected_type not in {'research-demand', 'technology-route', 'project-demand'}
        ):
            raise ServiceException(message='请选择有效的科研报告类型')
        template_key = parse_business_id(template_key) if template_key is not None else None
        row = await ResearchDao.get_template(db, template_key, user_id) if template_key is not None else None
        if template_key is not None and row is None:
            raise ServiceException(message='模板不存在或无权操作')
        if row is None:
            row = PipelineTemplateVersion(is_enabled=True, user_id=user_id)
            db.add(row)
        for field in ('name', 'description', 'model_id', 'image_model_id'):
            setattr(row, field, payload.get(field))
        # Older clients may omit the binding; preserve it on content-only updates.
        if purpose != 'research' or 'report_type' in payload or row.id is None:
            row.report_type = selected_type
        row.purpose, row.prompt = purpose, prompt
        row.sections = deepcopy(payload.get('sections') or [])
        row.image_config = deepcopy(payload.get('image_config') or {})
        row.is_enabled = bool(payload.get('is_enabled', True))
        await db.commit()
        await db.refresh(row)
        return cls._dict(row)

    @classmethod
    async def publish(cls, db, template_key, user_id=None, **_) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if not row:
            raise ServiceException(message='模板不存在或无权操作')
        row.is_enabled = True
        await db.commit()
        return cls._dict(row)

    @classmethod
    async def retire(cls, db, template_key, user_id=None) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if not row:
            raise ServiceException(message='模板不存在或无权操作')
        row.is_enabled = False
        await db.commit()
        return cls._dict(row)
