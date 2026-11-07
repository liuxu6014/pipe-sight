"""统一系统报告模板的显示名称，兼容旧配置但不修改历史文稿。"""


def display_template_name(name: str | None) -> str:
    if name == '科技项目需求填报表':
        return '科技项目需求表'
    return name or ''
