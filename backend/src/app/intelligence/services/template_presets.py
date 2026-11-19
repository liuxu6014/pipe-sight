"""Versioned built-ins, copied explicitly into an authenticated user's templates."""

import json
from copy import deepcopy
from pathlib import Path

from app.research.services.digest_document import DEFAULT_DIGEST_SCREENING


def default_digest_categories() -> list[dict]:
    return [
        {'name': '技术进展', 'prompt': '纳入本期公布的新方法、新材料、新设备或试验结果，说明具体创新及验证依据。'},
        {'name': '工程应用', 'prompt': '纳入本期投运、示范或改造的工程实践，关注应用场景、实施进展和运行成效。'},
        {'name': '行业动态', 'prompt': '纳入本期发布的行业政策、标准或重要市场变化，说明涉及对象和实际影响。'},
    ]


def effective_digest_categories(template) -> list[dict]:
    configured = getattr(template, 'screening_categories', None)
    if configured is not None:
        return deepcopy(configured)
    # A legacy user-written rule may describe topics outside the default categories.
    # Keep its free classification until the owner supplies named rules.
    preset = getattr(template, 'preset_key', None)
    general = (getattr(template, 'screening_prompt', None) or '').strip()
    if preset in {'digest-v1-weekly', 'digest-v1-monthly', 'digest-fixed-v1-weekly', 'digest-fixed-v1-monthly'} and (
        not general or general == DEFAULT_DIGEST_SCREENING
    ):
        return default_digest_categories()
    return []


def builtin_templates() -> list[dict]:
    path = Path(__file__).resolve().parents[4] / 'data/templates/research-presets-v1.json'
    rows = json.loads(path.read_text(encoding='utf-8'))['templates']
    # This versioned catalog's order is stable; identity survives user renaming.
    for index, row in enumerate(rows, 1):
        row['preset_key'] = f'research-v1-{index}'
    return rows


def fixed_digest_template(frequency: str) -> dict:
    """System-owned brief contract; never installed as an editable personal template."""
    label = {'weekly': '周报', 'monthly': '月报'}[frequency]
    return {
        'name': f'科技情报{label}',
        'preset_key': f'digest-fixed-v1-{frequency}',
        'purpose': 'digest',
        'digest_cadence': frequency,
        'report_type': None,
        'description': '使用统一简报格式，按类别组织事件及其摘要、行业洞察和来源。',
        'prompt': f'撰写科技情报{label}。只使用所选资料及已确认的覆盖周期。'
        '使用统一简报格式：标题、覆盖周期、按类别分组的编号事件；每个事件包含标题、摘要、发布日期、行业洞察和来源链接。'
        '按事件归纳事实、技术进展与业务影响，保留准确引用；不套用科研报告章节。'
        '历史资料只作背景，不冒充本期新进展；缺少证据不推测趋势，不编造事实和数据。',
        'sections': [],
        'model_id': None,
        'image_model_id': None,
        'image_config': {'enabled': False},
        'is_enabled': True,
    }


def personal_digest_presets() -> list[dict]:
    return [
        {
            **fixed_digest_template(frequency),
            'name': name,
            'preset_key': f'digest-v1-{frequency}',
            'screening_prompt': DEFAULT_DIGEST_SCREENING,
        }
        for frequency, name in (('weekly', '通用科技情报周报'), ('monthly', '通用科技情报月报'))
    ]
