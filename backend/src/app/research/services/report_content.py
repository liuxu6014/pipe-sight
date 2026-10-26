"""Provider document -> editable article, preserving actual paragraphs and sources."""

import json
import re

from app.business_time import format_business_time
from app.research.services.citation_format import REFERENCE_TITLES, clean_report_citations

MAX_SECTIONS = 100


def number_report_citations(content: str, citations: list[dict]) -> str:
    """Display reference ordinals, never database IDs. Preserve source identity."""
    aliases = {}
    for number, citation in enumerate(citations, 1):
        identity = str(citation.get('sourceId', citation.get('id', '')))
        aliases.setdefault(f'资料{identity}', []).append(number)
        if citation.get('type'):
            aliases.setdefault(f'{citation["type"]}:{identity}', []).append(number)

    def replace(match: re.Match[str]) -> str:
        value = match.group(1)
        tokens = re.findall(r'资料\d+|(?:article|paper|file):\d+', value)
        if not tokens or any(len(aliases.get(token, [])) != 1 for token in tokens):
            return match.group(0)
        numbers = list(dict.fromkeys(aliases[token][0] for token in tokens))
        note = re.sub(r'资料\d+|(?:article|paper|file):\d+', '', value).strip('；;,，、 ')
        return ''.join(f'[{number}]' for number in numbers) + (f'（{note}）' if note else '')

    numbered = re.sub(r'\[([^\]\n]+)\]', replace, content)
    # Models also mention evidence IDs in prose (e.g. 资料18新闻正文).
    # Do not rewrite an unresolved bracket a second time.
    def prose(match: re.Match[str]) -> str:
        value = match.group(0)
        if value.startswith('['):
            return value
        tokens = [f'资料{identity}' for identity in re.findall(r'\d+', value)]
        if any(len(aliases.get(token, [])) != 1 for token in tokens):
            return value
        return '、'.join(f'[{aliases[token][0]}]' for token in tokens)

    return re.sub(r'\[[^\]\n]+\]|资料\d+(?:[、，,]\d+)*', prose, numbered)


def _heading(value: str) -> str:
    # Saved editors may already number chapters. Never accumulate 1. 1. titles.
    return re.sub(r'^\d{1,2}[.、．]\s*', '', value.strip()).strip()


def sections_from_markdown(content: str) -> list[dict]:
    sections, lines, title = [], [], None
    fence = None

    def finish() -> None:
        body = '\n'.join(lines).strip()
        if title is not None or body:
            sections.append({'id': len(sections) + 1, 'title': title or '引言', 'content': body})

    for line in (content or '').splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append(line)
            continue
        match = re.match(r'^##\s+(.+?)\s*#*$', line) if fence is None else None
        if match:
            finish()
            title, lines = _heading(match.group(1)), []
        elif title is None and not lines and re.match(r'^#\s+', line):
            # The report title is rendered separately by the editor/exporter.
            continue
        else:
            lines.append(line)
    finish()
    if not sections:
        return [{'id': 1, 'title': '正文', 'content': ''}]
    if len(sections) == 1 and title is None:
        sections[0]['title'] = '正文'
    return sections


def _bibliography(materials: list[dict]) -> str:
    rows = []
    for material in materials:
        source = material.get('source') or {}
        source = source if isinstance(source, dict) else {}
        title = ' '.join(str(material.get('title') or '').split())
        identity = str(material['id'])
        kind = material.get('type')
        label = source.get('journal') or (
            '论文摘要' if kind == 'paper' else '新闻正文' if kind == 'article' else '用户资料'
        )
        published = source.get('published_date') or ''
        if not published and source.get('published_at'):
            published = format_business_time(source['published_at'])[:10]
        url = source.get('url') or (f'https://doi.org/{source["doi"]}' if source.get('doi') else '')
        parts = [f'[资料{identity}] {title}', str(label), str(published), str(url)]
        rows.append('；'.join(part for part in parts if part))
    return '\n\n'.join(rows)


def normalize_generated_report(content: str, materials: list[dict] | None = None) -> dict:  # noqa: PLR0912
    """Accept Markdown or a validated JSON article, never display transport JSON.

    Bibliographic rows come from the selected evidence, not model-proposed URLs
    or references. The caller retains raw provider output as the task result.
    """
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Generated report is empty')
    text = content.strip()
    wrapper = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, flags=re.DOTALL | re.IGNORECASE)
    candidate = wrapper.group(1).strip() if wrapper else text
    is_structured = candidate.startswith('{')
    if is_structured:
        try:
            document = json.loads(candidate)
        except (ValueError, RecursionError) as error:
            raise ValueError('Invalid structured report') from error
        if not isinstance(document, dict):
            raise ValueError('Structured report must be an object')
        raw_sections = document.get('sections')
        if raw_sections is None and isinstance(document.get('content'), str):
            return normalize_generated_report(document['content'], materials)
        if not isinstance(raw_sections, list) or not 1 <= len(raw_sections) <= MAX_SECTIONS:
            raise ValueError('Structured report needs nonempty bounded sections')
        sections = []
        intro = document.get('说明', document.get('introduction', document.get('summary', '')))
        if isinstance(intro, str) and intro.strip():
            sections.append({'title': '编制说明', 'content': intro.strip()})
        for section in raw_sections:
            if not isinstance(section, dict):
                raise ValueError('Invalid structured section')
            title, body = section.get('title'), section.get('content')
            if not isinstance(title, str) or not title.strip() or '\n' in title or '\r' in title:
                raise ValueError('Invalid section title')
            if not isinstance(body, str) or not body.strip():
                raise ValueError('Section requires actual text')
            sections.append({'title': _heading(title), 'content': body.strip()})
        text = '\n\n'.join(f'## {section["title"]}\n\n{section["content"]}' for section in sections)
    elif wrapper:
        # A JSON-labeled transport block cannot be accepted as an article body.
        raise ValueError('Structured report is not a document object')
    sections = sections_from_markdown(text)
    if materials and is_structured and not any(section['title'].casefold() in REFERENCE_TITLES for section in sections):
        text += '\n\n## 参考资料\n\n' + _bibliography(materials)
        sections = sections_from_markdown(text)
    if materials:
        text = number_report_citations(text, [
            {'sourceId': str(material['id']), 'type': material.get('type')} for material in materials
        ])
        sections = sections_from_markdown(text)
    # Store the canonical article, not merely a presentation-time cleanup.
    # Raw provider output remains intact on the generation task for diagnosis.
    text = clean_report_citations(text)
    sections = sections_from_markdown(text)
    return {'content': text, 'sections': sections}
