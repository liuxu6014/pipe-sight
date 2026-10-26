"""将本地 DeepSeek 配置安全注册到 PipeSight 的模型路由。

该脚本只创建缺失的模型和 ``data-filter`` 路由，不覆盖管理端已有配置。
API Key 只以 PipeSight 加密格式写入 ``ai_models``，脚本不会打印密钥。

运行方式（项目根目录）：

    cd backend
    uv run --no-sync python scripts/bootstrap_deepseek_route.py --env=dockerpg

支持的环境变量：

* ``PIPELINE_DEEPSEEK_API_KEY``（优先）或 ``INSIGHTHUB_LLM_API_KEYS``
* ``PIPELINE_DEEPSEEK_MODEL``（默认读取 ``INSIGHTHUB_LLM_MODEL``）
* ``PIPELINE_DEEPSEEK_BASE_URL``（默认读取 ``INSIGHTHUB_LLM_BASE_URL``）
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import select

from app.infrastructure.services.secret_crypto import SecretCrypto
from app.intelligence.models.ai_models import AiModels
from app.intelligence.models.configuration import PipelineModelRoute
from app.system.models.user import SysUser
from config.database import AsyncSessionLocal

DEEPSEEK_PROVIDER = 'DeepSeek'
DATA_FILTER_SCENE = 'data-filter'
DEFAULT_BASE_URL = 'https://api.deepseek.com/v1'


def _load_project_env() -> None:
    """在本地执行脚本时读取项目根目录的 .env，不覆盖显式环境变量。"""
    load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)


def _first_api_key() -> str:
    value = os.getenv('PIPELINE_DEEPSEEK_API_KEY', '').strip()
    if not value:
        value = next(
            (item.strip() for item in os.getenv('INSIGHTHUB_LLM_API_KEYS', '').split(',') if item.strip()),
            '',
        )
    if not value or value.startswith('<YOUR_'):
        raise RuntimeError('未找到 DeepSeek API Key，请先配置 PIPELINE_DEEPSEEK_API_KEY')
    return value


def _model_code() -> str:
    value = os.getenv('PIPELINE_DEEPSEEK_MODEL', '').strip() or os.getenv('INSIGHTHUB_LLM_MODEL', '').strip()
    if not value:
        raise RuntimeError('未找到 DeepSeek 模型编码，请配置 PIPELINE_DEEPSEEK_MODEL')
    return value


def _base_url() -> str:
    value = os.getenv('PIPELINE_DEEPSEEK_BASE_URL', '').strip() or os.getenv('INSIGHTHUB_LLM_BASE_URL', '').strip()
    value = value.rstrip('/')
    if not value:
        return DEFAULT_BASE_URL
    if value == 'https://api.deepseek.com':
        return DEFAULT_BASE_URL
    return value


async def main() -> None:
    _load_project_env()
    if AsyncSessionLocal is None:
        raise RuntimeError('数据库会话未初始化')

    model_code = _model_code()
    base_url = _base_url()
    encrypted_api_key = SecretCrypto.encrypt(_first_api_key())

    async with AsyncSessionLocal() as db:
        admin = (
            await db.execute(
                select(SysUser).where(SysUser.user_name == 'admin', SysUser.del_flag == '0')
            )
        ).scalars().first()
        if admin is None:
            raise RuntimeError('未找到启用的 admin 用户，无法确定模型配置归属')

        model = (
            await db.execute(
                select(AiModels).where(
                    AiModels.user_id == admin.user_id,
                    AiModels.provider == DEEPSEEK_PROVIDER,
                    AiModels.model_code == model_code,
                )
            )
        ).scalars().first()
        if model is None:
            model = AiModels(
                model_code=model_code,
                model_name=f'DeepSeek {model_code}',
                provider=DEEPSEEK_PROVIDER,
                model_sort=1,
                api_key=encrypted_api_key,
                base_url=base_url,
                model_type='chat',
                max_tokens=2048,
                temperature=0.2,
                support_reasoning='N',
                support_images='N',
                status='0',
                user_id=admin.user_id,
                create_by=admin.user_name,
                update_by=admin.user_name,
                create_time=datetime.now(),
                update_time=datetime.now(),
                remark='由 bootstrap_deepseek_route.py 创建；后续可在管理端维护',
            )
            db.add(model)
            await db.flush()
            model_action = 'created'
        else:
            model_action = 'reused'

        route = (
            await db.execute(
                select(PipelineModelRoute).where(PipelineModelRoute.scene == DATA_FILTER_SCENE)
            )
        ).scalars().first()
        if route is not None:
            if route.primary_model_id != model.model_id or not route.enabled:
                raise RuntimeError('data-filter 路由已存在，请在管理端确认后再修改，脚本不会覆盖已有路由')
            route_action = 'reused'
        else:
            route = PipelineModelRoute(
                route_id=f'route-{uuid4().hex}',
                scene=DATA_FILTER_SCENE,
                primary_model_id=model.model_id,
                timeout_seconds=30,
                max_tokens=2048,
                temperature=0.2,
                daily_limit=0,
                enabled=True,
                version_no=1,
                operator_id=admin.user_id,
                operator_name=admin.nick_name or admin.user_name,
                create_time=datetime.now(),
                update_time=datetime.now(),
            )
            db.add(route)
            route_action = 'created'

        await db.commit()
        print(
            {
                'model': model_code,
                'base_url': base_url,
                'model_action': model_action,
                'route_action': route_action,
                'scene': DATA_FILTER_SCENE,
                'api_key': 'encrypted',
            }
        )


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
