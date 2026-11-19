"""模板配置；旧发布接口只显式适配启停，不保留审批实体。"""

from copy import deepcopy
from typing import Any

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import load_only

from app.business_ids import parse_business_id, wire_id
from app.business_time import audit_now, format_business_time
from app.intelligence.models.configuration import PipelineTemplateVersion
from app.intelligence.services.template_presets import (
    default_digest_categories,
    effective_digest_categories,
    fixed_digest_template,
)
from app.research.models.research_models import PipelineDigestSchedule
from app.research.repositories.research_repository import ResearchDao
from app.research.services.digest_document import DEFAULT_DIGEST_SCREENING
from app.research.services.model_generation import ModelGateway
from app.research.services.report_labels import display_template_name, display_template_prompt
from exceptions.exception import ServiceException


class PipelineTemplateService:
    @classmethod
    async def install_builtins(cls, db, *, user_id: int, purpose='research') -> dict:
        from app.intelligence.services.template_presets import (  # noqa: PLC0415
            builtin_templates,
            personal_digest_presets,
        )

        # Prevent duplicate installation in simultaneous tabs, without blocking other users.
        if db.get_bind().dialect.name == 'postgresql':
            await db.execute(
                text('SELECT pg_advisory_xact_lock(hashtext(:key))'), {'key': f'template-presets:{user_id}'}
            )
        presets = personal_digest_presets() if purpose == 'digest' else builtin_templates()
        rows = list(
            await db.scalars(
                select(PipelineTemplateVersion)
                .options(
                    load_only(
                        PipelineTemplateVersion.id,
                        PipelineTemplateVersion.user_id,
                        PipelineTemplateVersion.preset_key,
                        PipelineTemplateVersion.purpose,
                        PipelineTemplateVersion.report_type,
                        PipelineTemplateVersion.name,
                        PipelineTemplateVersion.updated_at,
                    )
                )
                .where(
                    PipelineTemplateVersion.user_id == user_id,
                    or_(
                        PipelineTemplateVersion.preset_key.in_([preset['preset_key'] for preset in presets]),
                        PipelineTemplateVersion.name.in_([preset['name'] for preset in presets]),
                    ),
                )
            )
        )
        keys = {row.preset_key for row in rows if row.preset_key}
        existing = {(row.purpose, row.report_type, row.name): row for row in rows if not row.preset_key}
        created = []
        for preset in presets:
            if preset['preset_key'] in keys:
                continue
            previous = existing.get((preset['purpose'], preset['report_type'], preset['name']))
            if previous is not None:
                # Adopt an existing copy without changing its contents or edit time.
                await db.execute(
                    update(PipelineTemplateVersion)
                    .where(PipelineTemplateVersion.id == previous.id, PipelineTemplateVersion.user_id == user_id)
                    .values(
                        preset_key=preset['preset_key'],
                        updated_at=previous.updated_at,
                        **({'digest_cadence': preset['digest_cadence']} if preset.get('digest_cadence') else {}),
                    )
                )
                continue
            row = PipelineTemplateVersion(**deepcopy(preset), user_id=user_id)
            db.add(row)
            created.append(row)
        await db.commit()
        return {'created': len(created)}

    @staticmethod
    async def get_fixed_digest(db, frequency: str, user_id: int) -> PipelineTemplateVersion:
        """Internal format reference for existing report/schedule foreign keys.

        Historical user templates remain untouched. The caller owns the transaction,
        so failed admission rolls back creation of this internal reference too.
        """
        if frequency not in {'weekly', 'monthly'}:
            raise ServiceException(message='仅支持周报和月报固定格式')
        if user_id is None:
            raise ServiceException(message='简报所有者不能为空')
        if db.get_bind().dialect.name == 'postgresql':
            await db.execute(
                text('SELECT pg_advisory_xact_lock(hashtext(:key))'),
                {'key': f'fixed-digest:{user_id}:{frequency}'},
            )
        spec = fixed_digest_template(frequency)
        row = await db.scalar(
            select(PipelineTemplateVersion).where(
                PipelineTemplateVersion.user_id == user_id,
                PipelineTemplateVersion.preset_key == spec['preset_key'],
            )
        )
        if row is None:
            row = PipelineTemplateVersion(**deepcopy(spec), user_id=user_id)
            db.add(row)
            await db.flush()
        else:
            for field, value in spec.items():
                if getattr(row, field) != value:
                    setattr(row, field, deepcopy(value))
            row.deleted_at = None
        return row

    @staticmethod
    def is_fixed_digest(row) -> bool:
        return row.purpose == 'digest' and (getattr(row, 'preset_key', None) or '').startswith('digest-fixed-v1-')

    @classmethod
    def _manageable(cls, row) -> bool:
        return row.purpose != 'digest' or (
            not cls.is_fixed_digest(row) and getattr(row, 'digest_cadence', None) in {'weekly', 'monthly', 'all'}
        )

    @classmethod
    def _require_editable(cls, row) -> None:
        if not cls._manageable(row):
            raise ServiceException(message='系统默认模板和历史简报模板不可编辑')

    @classmethod
    async def get_digest_for_run(
        cls, db, frequency, user_id, template_id=None, *, legacy_schedule=False
    ) -> PipelineTemplateVersion:
        if template_id is None:
            return await cls.get_fixed_digest(db, frequency, user_id)
        row = await ResearchDao.get_template(db, template_id, user_id)
        if not row or row.purpose != 'digest':
            raise ServiceException(message='简报模板不存在或无权访问')
        if legacy_schedule and not cls._manageable(row) and not cls.is_fixed_digest(row):
            return await cls.get_fixed_digest(db, frequency, user_id)
        cls.validate_digest_cadence(row, frequency)
        if cls.is_fixed_digest(row):
            return await cls.get_fixed_digest(db, frequency, user_id)
        if not row.is_enabled or row.deleted_at is not None:
            raise ServiceException(message='请选择已启用的简报模板')
        return row

    @staticmethod
    def digest_cadence(row) -> str | None:
        """Explicit cadence is authoritative; legacy rows are converted by migration."""
        if row.purpose != 'digest':
            return None
        explicit = getattr(row, 'digest_cadence', None)
        if explicit:
            return explicit
        preset_cadence = {
            'digest-v1-weekly': 'weekly',
            'digest-v1-monthly': 'monthly',
        }.get(getattr(row, 'preset_key', None))
        if preset_cadence:
            return preset_cadence
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
    def _dict(row, *, include_prompt=True) -> dict:
        deleted_at = getattr(row, 'deleted_at', None)
        return {
            'id': wire_id(row.id),
            'templateKey': wire_id(row.id),
            'name': display_template_name(row.name),
            'purpose': row.purpose,
            'category': row.purpose,
            'reportType': getattr(row, 'report_type', None),
            'digestCadence': PipelineTemplateService.digest_cadence(row),
            **({'isSystemDefault': PipelineTemplateService.is_fixed_digest(row)} if row.purpose == 'digest' else {}),
            'description': row.description or '',
            **({'prompt': display_template_prompt(row.name, row.prompt)} if include_prompt else {}),
            **(
                {
                    'screeningPrompt': getattr(row, 'screening_prompt', None) or '',
                    'screeningCategories': effective_digest_categories(row),
                }
                if include_prompt and row.purpose == 'digest'
                else {}
            ),
            'modelId': wire_id(row.model_id),
            'imageModelId': wire_id(row.image_model_id),
            'sections': deepcopy(row.sections),
            'imageConfig': deepcopy(row.image_config),
            'isEnabled': row.is_enabled,
            'isDeleted': deleted_at is not None,
            'deletedAt': format_business_time(deleted_at) if deleted_at else None,
            'status': 'deleted' if deleted_at else 'published' if row.is_enabled else 'retired',
            'formats': ['docx', 'pdf'],
            'updatedAt': format_business_time(row.updated_at),
        }

    @staticmethod
    async def ensure_default_templates(db) -> None:
        # 启动时不创建共享模板；个人默认模板在已认证的列表入口按用户初始化。
        return None

    @classmethod
    async def list_templates(
        cls,
        db,
        category=None,
        published_only=False,
        user_id=None,
        include_deleted=False,
        *,
        page=None,
        page_size=10,
        keyword='',
        report_type=None,
        status='all',
    ) -> dict:
        purpose = {'project': 'research'}.get(category, category)
        counts = None
        if page is not None:
            from app.intelligence.repositories.template_repository import TemplateListDao  # noqa: PLC0415

            rows, total, counts = await TemplateListDao.page(
                db,
                user_id=user_id,
                purpose=purpose,
                report_type=report_type,
                keyword=keyword,
                status=status,
                published_only=published_only,
                page=page,
                page_size=page_size,
            )
        else:
            rows = await ResearchDao.list_templates(db, purpose, user_id)
        rows = [
            row
            for row in rows
            if cls._manageable(row)
            and (include_deleted or row.deleted_at is None)
            and (not published_only or (row.is_enabled and row.deleted_at is None))
        ]
        result = []
        for row in rows:
            model_id, image_id = await cls.generation_model_ids(db, row.purpose, row, {'enabled': True})
            model = await ResearchDao.get_model(db, model_id) if model_id is not None else None
            image = await ResearchDao.get_model(db, image_id) if image_id is not None else None
            result.append(
                {
                    **cls._dict(row, include_prompt=page is None),
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
        return {
            'rows': result,
            'total': total if page is not None else len(rows),
            **(
                {
                    'defaultScreeningPrompt': DEFAULT_DIGEST_SCREENING,
                    'defaultScreeningCategories': default_digest_categories(),
                }
                if purpose == 'digest'
                else {}
            ),
            **({'counts': counts} if counts is not None else {}),
            **(
                {
                    'defaultWritingPrompts': {
                        cadence: fixed_digest_template(cadence)['prompt'] for cadence in ('weekly', 'monthly')
                    }
                }
                if purpose == 'digest' and published_only
                else {}
            ),
        }

    @staticmethod
    async def get_published(db, template_key, user_id=None) -> PipelineTemplateVersion | None:
        if template_key is None:
            return None
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        return row if row and row.is_enabled and getattr(row, 'deleted_at', None) is None else None

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
            raise ServiceException(message=f'请联系管理员在模型管理的用途配置中选择启用且具备 text_generate 能力的{label}')
        if required and (image_config or {}).get('enabled') and image_id is None:
            raise ServiceException(message='请联系管理员在模型管理的用途配置中选择启用且具备 image_generate 能力的图片生成模型')
        return model_id, image_id

    @staticmethod
    async def validate_models(db, model_id, image_model_id=None, image_config=None) -> Any:
        model = await ResearchDao.get_model(db, model_id) if model_id is not None else None
        if not model or not model.is_enabled or 'text_generate' not in (model.capabilities or []):
            raise ServiceException(message='请联系管理员配置启用且具备 text_generate 能力的正文模型')
        if model.provider not in ModelGateway.supported_providers:
            raise ServiceException(message='正文模型原生协议不受支持，请联系管理员明确配置 compatible 端点')
        if (image_config or {}).get('enabled'):
            image = await ResearchDao.get_model(db, image_model_id) if image_model_id else None
            if not image or not image.is_enabled or 'image_generate' not in (image.capabilities or []):
                raise ServiceException(message='配图需由管理员配置启用且具备 image_generate 能力的模型')
            if image.provider not in ModelGateway.supported_providers:
                raise ServiceException(message='图片模型原生协议不受支持，请联系管理员明确配置 compatible 端点')
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
        if row is not None:
            cls._require_editable(row)
            if row.purpose != purpose:
                raise ServiceException(message='已有模板不能更改所属类型')
        if row is not None and row.deleted_at is not None:
            raise ServiceException(message='模板已删除，请先恢复后再编辑')
        cadence = payload.get('digest_cadence', cls.digest_cadence(row) if row is not None else None)
        if purpose == 'digest' and cadence not in {'weekly', 'monthly', 'all'}:
            raise ServiceException(message='请选择简报适用周期')
        if purpose != 'digest' and (
            cadence is not None or payload.get('screening_prompt') or payload.get('screening_categories') is not None
        ):
            raise ServiceException(message='选材筛选提示词、筛选类别和简报周期仅用于情报简报')
        if row is not None and (not bool(payload.get('is_enabled', True)) or cadence != row.digest_cadence):
            await cls._check_active_schedules(db, row)
        if row is None:
            row = PipelineTemplateVersion(is_enabled=True, user_id=user_id)
            db.add(row)
        for field in ('name', 'description', 'model_id', 'image_model_id'):
            setattr(row, field, payload.get(field))
        # Older clients may omit the binding; preserve it on content-only updates.
        if purpose != 'research' or 'report_type' in payload or row.id is None:
            row.report_type = selected_type
        row.digest_cadence = cadence
        if 'screening_prompt' in payload:
            row.screening_prompt = str(payload.get('screening_prompt') or '').strip() or None
        if 'screening_categories' in payload:
            row.screening_categories = deepcopy(payload['screening_categories'])
        row.purpose, row.prompt = purpose, prompt
        row.sections = deepcopy(payload.get('sections') or []) if purpose != 'digest' else []
        row.image_config = deepcopy(payload.get('image_config') or {}) if purpose != 'digest' else {'enabled': False}
        row.is_enabled = bool(payload.get('is_enabled', True))
        await db.commit()
        await db.refresh(row)
        return cls._dict(row)

    @staticmethod
    async def _check_active_schedules(db, row) -> None:
        schedules = list(
            await db.scalars(
                select(PipelineDigestSchedule)
                .where(
                    PipelineDigestSchedule.template_id == row.id,
                    PipelineDigestSchedule.user_id == row.user_id,
                    PipelineDigestSchedule.is_enabled.is_(True),
                )
                .with_for_update()
            )
        )
        if schedules:
            names = '、'.join(schedule.name for schedule in schedules[:5])
            raise ServiceException(
                message=f'模板正在被 {len(schedules)} 个启用的自动任务使用（{names}），请先停用这些任务再停用或删除模板'
            )

    @classmethod
    async def publish(cls, db, template_key, user_id=None, **_) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if not row or row.deleted_at is not None:
            raise ServiceException(message='模板不存在或无权操作')
        cls._require_editable(row)
        row.is_enabled = True
        await db.commit()
        return cls._dict(row)

    @classmethod
    async def retire(cls, db, template_key, user_id=None) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if not row:
            raise ServiceException(message='模板不存在或无权操作')
        cls._require_editable(row)
        await cls._check_active_schedules(db, row)
        row.is_enabled = False
        await db.commit()
        return cls._dict(row)

    @classmethod
    async def archive(cls, db, template_key, *, user_id: int) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if row is None:
            raise ServiceException(message='模板不存在或无权操作')
        cls._require_editable(row)
        await cls._check_active_schedules(db, row)
        row.deleted_at = row.deleted_at or audit_now()
        row.is_enabled = False
        await db.commit()
        return cls._dict(row)

    @classmethod
    async def restore(cls, db, template_key, *, user_id: int) -> dict:
        row = await ResearchDao.get_template(db, parse_business_id(template_key), user_id)
        if row is None:
            raise ServiceException(message='模板不存在或无权操作')
        cls._require_editable(row)
        row.deleted_at = None
        await db.commit()
        return cls._dict(row)
