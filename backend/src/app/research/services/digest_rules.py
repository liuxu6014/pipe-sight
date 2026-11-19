"""Compile the shared rule and the ordered category rules for one classification pass."""

from app.intelligence.services.template_presets import effective_digest_categories
from app.research.services.digest_document import DEFAULT_DIGEST_SCREENING


def combined_screening_prompt(general_prompt: str, categories: list[dict]) -> str:
    general = general_prompt.strip()
    if not categories:
        return general
    rules = '\n\n'.join(
        f'{index}. {rule["name"].strip()}\n{rule["prompt"].strip()}' for index, rule in enumerate(categories, 1)
    )
    parts = [f'通用要求\n{general}'] if general else []
    parts.extend(
        [
            f'分类规则\n{rules}',
            '逐篇判断。符合多个类别时选最符合的一个，匹配程度相同则取靠前的类别。没有匹配类别的文章排除。',
        ]
    )
    return '\n\n'.join(parts)


def screening_rule_snapshot(template, *, general_prompt=None, categories=None) -> dict:
    general = (general_prompt or '').strip() or getattr(template, 'screening_prompt', None) or DEFAULT_DIGEST_SCREENING
    rules = effective_digest_categories(template) if categories is None else categories
    return {'general_prompt': general, 'categories': rules, 'prompt': combined_screening_prompt(general, rules)}
