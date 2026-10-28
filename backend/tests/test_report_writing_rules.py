"""正文写作约束必须进入实际模型调用，不改动冻结任务配置。"""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import env as offline_env
from test_research_simplified_20261025 import no_external_network as offline_network

env = offline_env
no_external_network = offline_network


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['research', 'daily', 'weekly', 'monthly'])
async def test_actual_generation_call_requires_supported_claims_or_specific_questions(env, monkeypatch, kind):
    snapshot = {'title': '证据边界测试', 'type': kind, 'request': {}, 'model': {},
                'template': {'purpose': 'research' if kind == 'research' else 'digest', 'prompt': '', 'sections': []}}
    materials = [{'id': '24', 'type': 'paper', 'content': '导读摘要（据公开资料整理）：讨论检测局限。'}]
    original = deepcopy(materials)
    call = AsyncMock(return_value='正文')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(None, snapshot, materials, task_id=1)
    system = call.await_args.kwargs['system_prompt']
    assert '引用编号存在不代表该判断已有证据' in system
    assert '无充分依据的判断改成具体的待验证问题' in system
    assert '没有检索到资料不等于行业缺少方法' in system
    assert '研究目标不得把待验证的困难预设为已经存在' in system
    assert '二次导读只说明导读涉及什么' in system
    assert materials == original


@pytest.mark.asyncio
@pytest.mark.parametrize('purpose', ['research', 'article'])
async def test_legacy_structure_is_not_used_as_prose_prompt(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, purpose: str,
) -> None:
    legacy = {'name': '科技项目需求填报表', 'description': '研究需求',
              'sections': [{'title': '研究内容', 'words': 900}]}
    snapshot = {'title': '研究报告', 'type': purpose, 'request': {}, 'model': {},
                'template': {'purpose': purpose, 'prompt': json.dumps(legacy, ensure_ascii=False),
                             'sections': legacy['sections']}}
    original = deepcopy(snapshot)
    call = AsyncMock(return_value='正文')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(None, snapshot, [], task_id=1)
    system = call.await_args.kwargs['system_prompt']
    assert snapshot['template']['prompt'] not in system
    assert '观点—依据—分析' in system
    assert '不能作为该建议的文献依据' in system
    assert '不得为凑字数' in system
    assert snapshot == original


@pytest.mark.asyncio
async def test_administrator_prose_prompt_is_preserved(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = {'title': '日报', 'type': 'daily', 'request': {}, 'model': {},
                'template': {'purpose': 'digest', 'prompt': '每条简讯控制在两段以内。', 'sections': []}}
    call = AsyncMock(return_value='正文')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(None, snapshot, [], task_id=1)
    system = call.await_args.kwargs['system_prompt']
    assert system.startswith('每条简讯控制在两段以内。')
    assert '观点—依据—分析' not in system


@pytest.mark.asyncio
async def test_legacy_explicit_writing_text_is_not_lost(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = {'title': '研究报告', 'type': 'research', 'request': {}, 'model': {},
                'template': {'prompt': json.dumps({'sections': [], 'prompt': '专门讨论腐蚀机理',
                                                  'instructions': '比较方法局限'}), 'sections': []}}
    call = AsyncMock(return_value='正文')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(None, snapshot, [], task_id=1)
    system = call.await_args.kwargs['system_prompt']
    assert '专门讨论腐蚀机理' in system and '比较方法局限' in system
