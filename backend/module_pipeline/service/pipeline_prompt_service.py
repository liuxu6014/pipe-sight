from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.entity.do.pipeline_do import PipelinePromptVersion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PipelinePromptService:
    """管理管网业务提示词版本，并提供不依赖外部模型的离线结构测试。"""

    _allowed_scenes = frozenset({'research', 'digest', 'data-filter'})
    _allowed_variables = frozenset({'title', 'body', 'summary', 'source', 'publishedAt'})
    _default_prompt = {
        'prompt_key': 'data-filter',
        'scene': 'data-filter',
        'name': '数据过滤与清洗',
        'description': '对采集内容进行管网相关性、风险和发布资格筛选。',
        'system_prompt': (
            '你是管网科技情报过滤器。只能依据输入内容判断，不得补造事实。'
            '请输出 JSON：keep、score、reason、category、keywords。'
        ),
        'user_prompt': (
            '标题：{{title}}\n摘要：{{summary}}\n正文：{{body}}\n来源：{{source}}\n发布时间：{{publishedAt}}\n'
            '请判断是否保留，输出 keep（布尔）、score（0-100）、reason、category、keywords。'
        ),
    }

    @classmethod
    def _dict(cls, prompt: PipelinePromptVersion) -> dict[str, Any]:
        return {
            'id': prompt.prompt_id,
            'promptKey': prompt.prompt_key,
            'scene': prompt.scene,
            'name': prompt.name,
            'description': prompt.description,
            'systemPrompt': prompt.system_prompt,
            'userPrompt': prompt.user_prompt,
            'version': f'V{prompt.version_no}.0',
            'versionNo': prompt.version_no,
            'status': prompt.status,
            'testStatus': prompt.test_status,
            'testResult': dict(prompt.test_result or {}),
            'operator': prompt.operator_name,
            'publishedAt': prompt.published_at.isoformat() if prompt.published_at else None,
            'updatedAt': prompt.update_time.isoformat() if prompt.update_time else None,
        }

    @classmethod
    def _snapshot(cls, prompt: PipelinePromptVersion) -> dict[str, Any]:
        return {
            'promptKey': prompt.prompt_key,
            'versionNo': prompt.version_no,
            'scene': prompt.scene,
            'systemPrompt': prompt.system_prompt,
            'userPrompt': prompt.user_prompt,
            'executionMode': 'external-handoff',
        }

    @classmethod
    async def ensure_default_prompt(cls, db: AsyncSession) -> PipelinePromptVersion:
        existing = await PipelineDao.get_latest_prompt(db, cls._default_prompt['prompt_key'])
        if existing:
            return existing
        prompt = PipelinePromptVersion(
            prompt_id=f'prompt-{uuid4().hex[:16]}',
            version_no=1,
            status='published',
            test_status='passed',
            test_result={'mode': 'offline-template', 'message': '内置默认过滤 Prompt 已通过结构测试。'},
            operator_name='系统默认',
            published_at=datetime.now(),
            **cls._default_prompt,
        )
        await PipelineDao.add_prompt(db, prompt)
        return prompt

    @classmethod
    async def list_prompts(cls, db: AsyncSession, scene: str | None = None) -> dict[str, Any]:
        rows = await PipelineDao.list_prompt_versions(db, scene=scene)
        latest: dict[str, PipelinePromptVersion] = {}
        for row in rows:
            latest.setdefault(row.prompt_key, row)
        return {'rows': [cls._dict(item) for item in latest.values()], 'total': len(latest)}

    @classmethod
    async def save_draft(
        cls,
        db: AsyncSession,
        *,
        prompt_key: str,
        scene: str,
        name: str,
        description: str,
        system_prompt: str,
        user_prompt: str,
        operator_id: int,
        operator_name: str,
    ) -> dict[str, Any]:
        if scene not in cls._allowed_scenes:
            raise ServiceException(message='提示词业务场景不合法')
        if not prompt_key.strip() or not name.strip() or not system_prompt.strip() or not user_prompt.strip():
            raise ServiceException(message='提示词名称、系统提示词和用户提示词不能为空')
        latest = await PipelineDao.get_latest_prompt(db, prompt_key)
        prompt = PipelinePromptVersion(
            prompt_id=f'prompt-{uuid4().hex[:16]}',
            prompt_key=prompt_key.strip(),
            scene=scene,
            name=name.strip(),
            description=description.strip(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            version_no=(latest.version_no + 1) if latest else 1,
            status='draft',
            test_status='untested',
            test_result={},
            operator_id=operator_id,
            operator_name=operator_name,
        )
        await PipelineDao.add_prompt(db, prompt)
        await db.commit()
        await db.refresh(prompt)
        return cls._dict(prompt)

    @classmethod
    async def test_prompt(cls, db: AsyncSession, prompt_key: str) -> dict[str, Any]:
        prompt = await PipelineDao.get_latest_prompt(db, prompt_key)
        if not prompt:
            raise ServiceException(message='提示词不存在')
        content = f'{prompt.system_prompt}\n{prompt.user_prompt}'
        variables = set(re.findall(r'\{\{\s*([A-Za-z][A-Za-z0-9]*)\s*\}\}', content))
        unknown = sorted(variables - cls._allowed_variables)
        missing = sorted({'title', 'body'} - variables)
        missing_output = [name for name in ('keep', 'score', 'reason') if name not in content]
        if unknown or missing or missing_output:
            message = '；'.join(
                part
                for part in (
                    f'存在未支持变量：{", ".join(unknown)}' if unknown else '',
                    f'缺少必要变量：{", ".join(missing)}' if missing else '',
                    f'缺少过滤输出字段：{", ".join(missing_output)}' if missing_output else '',
                )
                if part
            )
            prompt.test_status = 'failed'
            prompt.test_result = {'mode': 'offline-template', 'message': message}
            if hasattr(db, 'commit'):
                await db.commit()
            raise ServiceException(message=message)
        prompt.test_status = 'passed'
        prompt.test_result = {
            'mode': 'offline-template',
            'message': '变量和过滤输出结构检查通过，尚未调用外部模型。',
            'variables': sorted(variables),
        }
        await db.commit()
        await db.refresh(prompt)
        return cls._dict(prompt)

    @classmethod
    async def publish_prompt(
        cls,
        db: AsyncSession,
        prompt_key: str,
        *,
        operator_id: int,
        operator_name: str,
    ) -> dict[str, Any]:
        prompt = await PipelineDao.get_latest_prompt(db, prompt_key)
        if not prompt:
            raise ServiceException(message='提示词不存在')
        if prompt.test_status != 'passed':
            raise ServiceException(message='提示词必须先通过离线结构测试才能发布')
        versions = await PipelineDao.list_prompt_versions(db, prompt_key=prompt_key)
        for item in versions:
            if item.status == 'published':
                item.status = 'retired'
        prompt.status = 'published'
        prompt.operator_id = operator_id
        prompt.operator_name = operator_name
        prompt.published_at = datetime.now()
        await db.commit()
        await db.refresh(prompt)
        return cls._dict(prompt)

    @classmethod
    async def get_published_prompt(cls, db: AsyncSession, prompt_key: str) -> PipelinePromptVersion | None:
        return await PipelineDao.get_published_prompt(db, prompt_key)

    @classmethod
    async def get_published_snapshot(cls, db: AsyncSession, prompt_key: str) -> dict[str, Any] | None:
        prompt = await cls.get_published_prompt(db, prompt_key)
        return cls._snapshot(prompt) if prompt else None
