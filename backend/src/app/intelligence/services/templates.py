"""模板配置；旧发布接口只显式适配启停，不保留审批实体。"""

from copy import deepcopy

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.intelligence.models.configuration import PipelineTemplateVersion
from app.research.repositories.research_repository import ResearchDao
from app.research.services.model_generation import ModelGateway
from exceptions.exception import ServiceException


class PipelineTemplateService:
    @staticmethod
    def digest_cadence(row):
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
    def validate_digest_cadence(cls, row, frequency):
        if cls.digest_cadence(row) not in {frequency, 'all'}:
            raise ServiceException(message='模板周期未知或与简报周期不匹配，请选择明确适用周期的模板')

    @staticmethod
    def effective_image_config(template_config, request):
        config = deepcopy(template_config or {})
        options = request.get('options') or {}
        # 顶层显式选择优先；未提交才读取旧客户端选项，再回落模板默认。
        if 'diagram' in request:
            config['enabled'] = request['diagram']
        elif 'generateImages' in options:
            config['enabled'] = options['generateImages']
        return config

    @staticmethod
    def _dict(row):
        return {
            'id': wire_id(row.id),
            'templateKey': wire_id(row.id),
            'name': row.name,
            'purpose': row.purpose,
            'category': row.purpose,
            'reportType': row.purpose,
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
    async def ensure_default_templates(db):
        # 默认模板由迁移映射；运行时不自动创建模板或模型配置。
        return None

    @classmethod
    async def list_templates(cls, db, category=None, published_only=False):
        purpose = {'project': 'research'}.get(category, category)
        rows = await ResearchDao.list_templates(db, purpose)
        rows = [row for row in rows if not published_only or row.is_enabled]
        result = []
        for row in rows:
            model = await ResearchDao.get_model(db, row.model_id) if row.model_id is not None else None
            image = await ResearchDao.get_model(db, row.image_model_id) if row.image_model_id is not None else None
            result.append(
                {
                    **cls._dict(row),
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
    async def get_published(db, template_key):
        if template_key is None:
            return None
        row = await ResearchDao.get_template(db, parse_business_id(template_key))
        return row if row and row.is_enabled else None

    @staticmethod
    async def validate_models(db, model_id, image_model_id=None, image_config=None):
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
    async def save_draft(cls, db, *, template_key, payload, operator_id, operator_name):
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
        template_key = parse_business_id(template_key) if template_key is not None else None
        row = await ResearchDao.get_template(db, template_key) if template_key is not None else None
        if template_key is not None and row is None:
            raise ServiceException(message='模板不存在')
        if row is None:
            row = PipelineTemplateVersion(is_enabled=True)
            db.add(row)
        for field in ('name', 'description', 'model_id', 'image_model_id'):
            setattr(row, field, payload.get(field))
        row.purpose, row.prompt = purpose, prompt
        row.sections = deepcopy(payload.get('sections') or [])
        row.image_config = deepcopy(payload.get('image_config') or {})
        row.is_enabled = bool(payload.get('is_enabled', True))
        await db.commit()
        await db.refresh(row)
        return cls._dict(row)

    @classmethod
    async def publish(cls, db, template_key, **_):
        row = await ResearchDao.get_template(db, parse_business_id(template_key))
        if not row:
            raise ServiceException(message='模板不存在')
        row.is_enabled = True
        await db.commit()
        return cls._dict(row)

    @classmethod
    async def retire(cls, db, template_key):
        row = await ResearchDao.get_template(db, parse_business_id(template_key))
        if not row:
            raise ServiceException(message='模板不存在')
        row.is_enabled = False
        await db.commit()
        return cls._dict(row)
