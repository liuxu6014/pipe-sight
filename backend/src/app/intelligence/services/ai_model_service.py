"""管理员维护一张模型表；DTO 兼容不传递给 ORM。"""

from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import urlsplit

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.services.secret_crypto import SecretCrypto
from app.intelligence.models.ai_models import AiModels
from app.intelligence.schemas.ai_model import AiModelModel, AiModelTestResultModel
from app.research.services.model_generation import ModelGateway
from common.http.schemas import CrudResponseModel, PageModel
from exceptions.exception import ServiceException


class AiModelService:
    @staticmethod
    def public(row):
        # 不返回 credential_ref 密文/引用，不回传凭证；只告知已配置。
        return AiModelModel(
            id=row.id,
            name=row.name,
            provider=row.provider,
            code=row.code,
            base_url=row.base_url,
            credential_ref=None,
            capabilities=row.capabilities,
            parameters=row.parameters,
            is_enabled=row.is_enabled,
            model_id=row.id,
            model_name=row.name,
            model_code=row.code,
            status='0' if row.is_enabled else '1',
            model_type='image'
            if 'image_generate' in row.capabilities and 'text_generate' not in row.capabilities
            else 'text',
            support_images='Y' if 'image_input' in row.capabilities else 'N',
            support_reasoning='Y' if 'reasoning' in row.capabilities else 'N',
            max_tokens=row.parameters.get('max_tokens'),
            temperature=row.parameters.get('temperature'),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @classmethod
    async def get_ai_model_list_services(cls, query_db, query_object, data_scope_sql=True, is_page=False):
        query = select(AiModels).order_by(AiModels.id)
        if query_object.model_id is not None:
            query = query.where(AiModels.id == query_object.model_id)
        if query_object.model_name:
            query = query.where(AiModels.name.contains(query_object.model_name))
        if query_object.provider:
            query = query.where(AiModels.provider == query_object.provider)
        if query_object.status:
            query = query.where(AiModels.is_enabled.is_(query_object.status == '0'))
        rows = list(await query_db.scalars(query))
        if query_object.capability:
            rows = [r for r in rows if query_object.capability in r.capabilities]
        total = len(rows)
        if is_page:
            start = (query_object.page_num - 1) * query_object.page_size
            rows = rows[start : start + query_object.page_size]
        data = [cls.public(row).model_dump(by_alias=True) for row in rows]
        return (
            PageModel(
                rows=data,
                total=total,
                pageNum=query_object.page_num,
                pageSize=query_object.page_size,
                hasNext=query_object.page_num * query_object.page_size < total,
            )
            if is_page
            else data
        )

    @staticmethod
    async def check_ai_model_data_scope_services(query_db, model_id, data_scope_sql=True):
        # 管理员权限由路由鉴权；不存在按真实实体判断。
        if not await query_db.get(AiModels, model_id):
            raise ServiceException(message='AI模型不存在')
        return CrudResponseModel(is_success=True, message='校验通过')

    @staticmethod
    def values(dto, current=None):
        result = {}
        for name in ('name', 'provider', 'code', 'base_url', 'capabilities', 'parameters', 'is_enabled'):
            value = getattr(dto, name)
            if value is not None:
                result[name] = value
        params = dict(result.get('parameters', current.parameters if current else {}) or {})
        if dto.max_tokens is not None:
            params['max_tokens'] = dto.max_tokens
        if dto.temperature is not None:
            params['temperature'] = dto.temperature
        result['parameters'] = params
        if dto.api_key and not dto.api_key.startswith('***'):
            result['credential_ref'] = 'encrypted:' + SecretCrypto.encrypt(dto.api_key)
        elif dto.credential_ref:
            if not dto.credential_ref.startswith(('env:', 'encrypted:')):
                raise ServiceException(message='凭证须为 env: 环境变量引用或本地加密引用')
            result['credential_ref'] = dto.credential_ref
        for name in ('name', 'provider', 'code', 'base_url', 'credential_ref', 'capabilities'):
            value = result.get(name, getattr(current, name, None) if current else None)
            if value is None or (isinstance(value, str) and not value.strip()) or value == []:
                raise ServiceException(message=f'模型必填配置缺失：{name}')
        endpoint = urlsplit(result.get('base_url', current.base_url if current else ''))
        if result.get('provider', current.provider if current else None) not in ModelGateway.supported_providers:
            raise ServiceException(message='仅支持 OpenAI 兼容协议；请为兼容端点选择 compatible')
        if (
            endpoint.scheme not in {'https', 'http'}
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise ServiceException(message='模型地址必须为有效 HTTP(S) 基础地址')
        if (
            not 1 <= int(params.get('timeout_seconds', 60)) <= 120
            or not 1 <= int(params.get('max_tokens', 2048)) <= 32768
            or not 0 <= float(params.get('temperature', 0.2)) <= 2
        ):
            raise ServiceException(message='模型超时、Token 或温度参数超出范围')
        if int(params.get('daily_limit', 0)) < 0 or not 1 <= int(params.get('context_chars', 100000)) <= 2000000:
            raise ServiceException(message='模型配额或上下文预算不合法')
        # 参数白名单禁止把凭证/任意正文塞入任务快照。
        allowed = {
            'timeout_seconds',
            'max_tokens',
            'temperature',
            'daily_limit',
            'context_chars',
            'max_response_bytes',
            'size',
            'quality',
            'style',
        }
        if set(params) - allowed:
            raise ServiceException(message='存在不支持的模型参数')
        return result

    @classmethod
    async def add_ai_model_services(cls, query_db, page_object):
        values = cls.values(page_object)
        values.setdefault('is_enabled', True)
        query_db.add(AiModels(**values))
        await query_db.commit()
        return CrudResponseModel(is_success=True, message='新增成功')

    @classmethod
    async def edit_ai_model_services(cls, query_db, page_object):
        row = await query_db.get(AiModels, page_object.id)
        if not row:
            raise ServiceException(message='AI模型不存在')
        for name, value in cls.values(page_object, row).items():
            setattr(row, name, value)
        await query_db.commit()
        return CrudResponseModel(is_success=True, message='修改成功')

    @classmethod
    async def ai_model_detail_services(cls, query_db, model_id):
        row = await query_db.get(AiModels, model_id)
        if not row:
            raise ServiceException(message='AI模型不存在')
        return cls.public(row)

    @staticmethod
    async def delete_ai_model_services(query_db, page_object):
        try:
            ids = [int(item) for item in page_object.model_ids.split(',')]
            await query_db.execute(delete(AiModels).where(AiModels.id.in_(ids)))
            await query_db.commit()
        except IntegrityError:
            await query_db.rollback()
            raise ServiceException(message='模型已被模板或资源引用，请停用而非删除') from None
        return CrudResponseModel(is_success=True, message='删除成功')

    @staticmethod
    async def test_ai_model_services(query_db, model_id, data_scope_sql=True, capability='text_generate'):
        row = await query_db.get(AiModels, model_id)
        if not row:
            raise ServiceException(message='AI模型不存在')
        start = perf_counter()
        snapshot = {
            'id': row.id,
            'code': row.code,
            'provider': row.provider,
            'base_url': row.base_url,
            'parameters': row.parameters,
        }
        try:
            content = await ModelGateway.call(
                query_db,
                snapshot,
                capability=capability,
                prompt='生成一张纯色蓝色方块' if capability == 'image_generate' else '请仅回复 OK。',
            )
        except Exception:
            await query_db.commit()
            raise
        await query_db.commit()
        return AiModelTestResultModel(
            model_id=row.id,
            model_code=row.code,
            provider=row.provider,
            success=True,
            latency_ms=round((perf_counter() - start) * 1000),
            capability=capability,
            response_preview=f'已验证图片 {len(content)} 字节' if isinstance(content, bytes) else content[:240],
            message='模型真实调用测试成功',
            tested_at=datetime.now(timezone.utc),
        )
