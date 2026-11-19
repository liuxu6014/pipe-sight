"""统一系统报告模板的显示名称，兼容旧配置但不修改历史文稿。"""

LEGACY_DIGEST_TEMPLATE_NAMES = {
    '管网科技情报周报': '科技情报周报',
    '管网科技情报月报': '科技情报月报',
}


def display_template_name(name: str | None) -> str:
    if name == '科技项目需求填报表':
        return '科技项目需求表'
    return LEGACY_DIGEST_TEMPLATE_NAMES.get(name or '', name or '')


def display_template_prompt(name: str, prompt: str) -> str:
    prefix = f'撰写{name}。'
    if name in LEGACY_DIGEST_TEMPLATE_NAMES and prompt.startswith(prefix):
        return f'撰写{LEGACY_DIGEST_TEMPLATE_NAMES[name]}。' + prompt.removeprefix(prefix)
    return prompt
