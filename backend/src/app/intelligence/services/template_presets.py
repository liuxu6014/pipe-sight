"""Versioned built-ins, copied explicitly into an authenticated user's templates."""

import json
from pathlib import Path


def builtin_templates() -> list[dict]:
    path = Path(__file__).resolve().parents[4] / 'data/templates/research-presets-v1.json'
    rows = json.loads(path.read_text(encoding='utf-8'))['templates']
    for label in ('日报', '周报', '月报'):
        rows.append(
            {
                'name': f'管网科技情报{label}',
                'purpose': 'digest',
                'report_type': None,
                'description': f'依据所选周期的公开资讯编制科技情报{label}，区分本期进展和历史背景。',
                'prompt': f'撰写管网科技情报{label}。只使用所选资料及已确认的覆盖周期。'
                '按栏目组织完整自然段，说明事件、技术进展与业务影响，保留句末引用。'
                '历史资料只作背景，不冒充本期新进展；缺少证据不推测趋势，不编造事实和数据。',
                'sections': [
                    {
                        'id': index,
                        'title': title,
                        'words': 600,
                        'required': True,
                        'description': '仅依据已选资料归纳事实、适用场景和局限，保留准确引用。',
                    }
                    for index, title in enumerate(('本期要闻', '技术进展', '应用与研判'), 1)
                ],
                'model_id': None,
                'image_model_id': None,
                'image_config': {'enabled': False},
                'is_enabled': True,
            }
        )
    return rows
