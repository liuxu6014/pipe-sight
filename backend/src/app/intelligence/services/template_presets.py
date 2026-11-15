"""Versioned built-ins, copied explicitly into an authenticated user's templates."""

import json
from pathlib import Path


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
        'name': f'管网科技情报{label}',
        'preset_key': f'digest-fixed-v1-{frequency}',
        'purpose': 'digest',
        'digest_cadence': frequency,
        'report_type': None,
        'description': '使用统一简报格式，按类别组织事件及其摘要、行业洞察和来源。',
        'prompt': f'撰写管网科技情报{label}。只使用所选资料及已确认的覆盖周期。'
        '使用统一简报格式：标题、覆盖周期、按类别分组的编号事件；每个事件包含标题、摘要、发布日期、行业洞察和来源链接。'
        '按事件归纳事实、技术进展与业务影响，保留准确引用；不套用科研报告章节。'
        '历史资料只作背景，不冒充本期新进展；缺少证据不推测趋势，不编造事实和数据。',
        'sections': [],
        'model_id': None,
        'image_model_id': None,
        'image_config': {'enabled': False},
        'is_enabled': True,
    }
