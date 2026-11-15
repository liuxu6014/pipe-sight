"""Provider document -> editable article, preserving actual paragraphs and sources."""

import json
import re
from typing import NoReturn

from app.business_time import format_business_time
from app.research.services.citation_format import REFERENCE_TITLES, clean_report_citations
from app.research.services.digest_document import is_digest_body
from app.research.services.project_demand_document import PROJECT_DEMAND_FORMAT, unnumbered_chapter

MAX_SECTIONS = 100
DELIVERY_REFERENCE_TITLES = REFERENCE_TITLES | {'来源清单', '资料来源'}

_BOLD_HEADING_RE = re.compile(r'^\*\*(.+?)\*\*\s*$')
_LEGACY_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*#*$')


def _section_heading(line: str) -> str | None:
    """Return the section title if the line is a section heading, else None.

    Section headings are the bold form ``**标题**`` or the legacy Markdown
    ``## 标题`` (kept so previously saved reports still parse into sections).
    """
    bold = _BOLD_HEADING_RE.match(line)
    if bold:
        return _heading(bold.group(1))
    legacy = re.match(r'^##\s+(.+?)\s*#*$', line)
    if legacy:
        return _heading(legacy.group(1))
    return None


def _heading_info(line: str) -> tuple[int, str] | None:
    """Level and cleaned title for a bold or legacy Markdown heading line."""
    bold = _BOLD_HEADING_RE.match(line)
    if bold:
        return 2, _heading(bold.group(1))
    legacy = _LEGACY_HEADING_RE.match(line)
    if legacy:
        return len(legacy.group(1)), _heading(legacy.group(2))
    return None


def _strip_item_heading(line: str) -> str:
    """Legacy ``### item`` (and deeper) becomes a plain-text subheading."""
    match = re.match(r'^#{3,6}\s+(.+?)\s*#*$', line)
    return _heading(match.group(1)) if match else line


def _strip_item_headings(text: str) -> str:
    return '\n'.join(_strip_item_heading(line) for line in text.splitlines())


def _normalize_headings(text: str) -> str:
    """Convert Markdown ``#`` headings to the hash-free article convention.

    ``## 标题`` becomes a bold section line ``**标题**``; ``### 标题`` and
    deeper become plain subheadings; the single-hash report title is dropped
    because the editor and exporters render the title separately.
    """
    lines: list[str] = []
    for line in text.splitlines():
        match = _LEGACY_HEADING_RE.match(line)
        if not match:
            lines.append(line)
            continue
        level = len(match.group(1))
        name = _heading(match.group(2))
        if level == 1:
            continue
        lines.append(f'**{name}**' if level == 2 else line if level == 3 and is_digest_body(text) else name)  # noqa: PLR2004
    return '\n'.join(lines)


class ManuscriptValidationError(ValueError):
    """Only application-authored validation messages, safe for task errors."""


def validate_generated_article(content: str, materials: list[dict] | None = None, *, require_citations=True) -> None:
    """Check document integrity, not the truth or sufficiency of its claims.

    Draft edits intentionally do not pass this gate. An invalid generated
    result must not replace a user's saved article or be labelled complete.
    """

    def reject(reason) -> NoReturn:
        raise ManuscriptValidationError(f'文稿检查未通过：{reason}；请调整资料或大纲后重试')

    if not content.strip():
        reject('正文为空')
    if re.search(r'^\s*(?:`{3,}|~{3,})', content, re.MULTILINE):
        reject('正文残留代码围栏，不能作为完整文章')
    if re.search(r'</?(?:html|body|script|div|p|span)\b[^>]*>', content, re.IGNORECASE):
        reject('正文残留 HTML 标记')
    body_lines, reference_level = [], None
    sections = []
    for line in content.splitlines():
        heading = _heading_info(line)
        if heading:
            level, name = heading[0], heading[1].casefold()
            if reference_level is not None and level > reference_level:
                continue
            reference_level = level if name in DELIVERY_REFERENCE_TITLES else None
            while sections and sections[-1]['level'] >= level:
                if not sections.pop()['has_body']:
                    reject('存在空章节')
            if reference_level is None and level >= 2:  # noqa: PLR2004
                sections.append({'level': level, 'has_body': False})
            continue
        if reference_level is None:
            body_lines.append(line)
            if line.strip():
                for section in sections:
                    section['has_body'] = True
    if any(not section['has_body'] for section in sections):
        reject('存在空章节')
    body = '\n'.join(body_lines).strip()
    if not body:
        reject('缺少实际正文')
    if re.search(r'\[(?:资料\d+|(?:article|paper|file):\d+)[^\]\n]*\]', body):
        reject('包含无法对应选材的来源编号')
    # A numeric Markdown link is a link, not an evidence citation.
    prose = re.sub(r'\[[^\]\n]*\]\([^\n)]*\)', '', body)
    ordinals = [int(value) for value in re.findall(r'\[(-?\d+)\]', prose)]
    if any(number < 1 for number in ordinals) or (
        materials is not None and any(number > len(materials) for number in ordinals)
    ):
        reject('引用序号超出实际资料范围')
    if require_citations and materials and not ordinals:
        reject('正文未引用所选资料，不能仅附来源清单')


def _without_model_references(text: str) -> str:
    lines, reference_level, fence = [], None, None
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        heading = _heading_info(line) if fence is None else None
        if heading:
            level, name = heading[0], heading[1].casefold()
            if reference_level is not None and level <= reference_level:
                reference_level = None
            if name in DELIVERY_REFERENCE_TITLES:
                reference_level = level
        if reference_level is None:
            lines.append(line)
    return '\n'.join(lines).strip()


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
        if fence is not None:
            lines.append(line)
            continue
        name = _section_heading(line)
        if name is not None:
            finish()
            title, lines = name, []
        elif title is None and not lines and re.match(r'^#\s+', line):
            # The report title is rendered separately by the editor/exporter.
            continue
        else:
            lines.append(line if is_digest_body(content) else _strip_item_heading(line))
    finish()
    if not sections:
        return [{'id': 1, 'title': '正文', 'content': ''}]
    if len(sections) == 1 and title is None:
        sections[0]['title'] = '正文'
    return sections


def _bibliography(materials: list[dict], *, numbered=False) -> str:
    rows = []
    for index, material in enumerate(materials, 1):
        source = material.get('source') or {}
        source = source if isinstance(source, dict) else {}
        title = ' '.join(str(material.get('title') or '').split())
        identity = str(material['id'])
        kind = material.get('type')
        label = (
            source.get('journal')
            or source.get('publisher')
            or source.get('name')
            or ('论文摘要' if kind == 'paper' else '新闻正文' if kind == 'article' else '用户资料')
        )
        published = source.get('published_date') or ''
        if not published and source.get('published_at'):
            published = format_business_time(source['published_at'])[:10]
        url = source.get('url') or (f'https://doi.org/{source["doi"]}' if source.get('doi') else '')
        authors = source.get('authors') or ''
        if isinstance(authors, (list, tuple)):
            authors = '、'.join(str(author) for author in authors)
        ordinal = str(index) if numbered else f'资料{identity}'
        parts = [f'[{ordinal}] {title}', str(authors), str(label), str(published), str(url)]
        rows.append('；'.join(part for part in parts if part))
    return '\n\n'.join(rows)


def normalize_generated_report(content: str, materials: list[dict] | None = None, *, delivery: bool = False) -> dict:
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
        if document.get('format') == 'digest-reference-v1':
            from app.research.services.digest_document import normalize_digest_document  # noqa: PLC0415

            return normalize_digest_document(candidate, materials)
        raw_sections = document.get('sections')
        if raw_sections is None and isinstance(document.get('content'), str):
            return normalize_generated_report(document['content'], materials, delivery=delivery)
        if not isinstance(raw_sections, list) or not 1 <= len(raw_sections) <= MAX_SECTIONS:
            raise ValueError('Structured report needs nonempty bounded sections')
        sections = []
        intro = document.get('说明', document.get('introduction', document.get('summary', '')))
        if isinstance(intro, str) and intro.strip():
            sections.append({'title': '摘要' if delivery else '编制说明', 'content': intro.strip()})
        for section in raw_sections:
            if not isinstance(section, dict):
                raise ValueError('Invalid structured section')
            title, body = section.get('title'), section.get('content')
            if not isinstance(title, str) or not title.strip() or '\n' in title or '\r' in title:
                raise ValueError('Invalid section title')
            if not isinstance(body, str) or not body.strip():
                raise ValueError('Section requires actual text')
            sections.append({'title': _heading(title), 'content': _strip_item_headings(body.strip())})
        text = '\n\n'.join(f'**{section["title"]}**\n\n{section["content"]}' for section in sections)
    elif wrapper:
        # A JSON-labeled transport block cannot be accepted as an article body.
        raise ValueError('Structured report is not a document object')
    else:
        # Recognize reference sections before legacy heading levels are flattened.
        # Otherwise a #/### reference heading can leave model-invented sources in prose.
        text = _normalize_headings(_without_model_references(text) if delivery and materials else text)
    if delivery:
        # Remove only parameter rows in the generated preamble. Do not redact
        # narrative limitations or rewrite historical/user-authored reports.
        lines, in_preamble = [], True
        for line in text.splitlines():
            if _section_heading(line) is not None:
                in_preamble = False
            if in_preamble and re.match(
                r'^\s*(?:报告周期|研究方向|关键词|条目数|来源范围|报告模板|生成设置)\s*[：:]', line
            ):
                continue
            lines.append(line)
        text = '\n'.join(lines).strip()
        if materials:
            sections = sections_from_markdown(_without_model_references(text))
            text = '\n\n'.join(f'**{section["title"]}**\n\n{section["content"]}' for section in sections)
            text += '\n\n**参考资料**\n\n' + _bibliography(materials)
    sections = sections_from_markdown(text)
    if materials and is_structured and not any(section['title'].casefold() in REFERENCE_TITLES for section in sections):
        text += '\n\n**参考资料**\n\n' + _bibliography(materials)
        sections = sections_from_markdown(text)
    if materials:
        text = number_report_citations(
            text, [{'sourceId': str(material['id']), 'type': material.get('type')} for material in materials]
        )
        sections = sections_from_markdown(text)
    # Store the canonical article, not merely a presentation-time cleanup.
    # Raw provider output remains intact on the generation task for diagnosis.
    text = clean_report_citations(text)
    sections = sections_from_markdown(text)
    return {'content': text, 'sections': sections}


def normalize_task_report(content: str, materials: list[dict], snapshot: dict) -> dict:
    if snapshot.get('document_format') != PROJECT_DEMAND_FORMAT:
        article = normalize_generated_report(content, materials, delivery=True)
        request = snapshot.get('request') or {}
        outline = request.get('outline') or (snapshot.get('template') or {}).get('sections') or []
        sections = article['sections']
        expected = [unnumbered_chapter(str(item['title'])) for item in outline]
        remaining = [s for s in sections[1:] if s['title'].casefold() not in DELIVERY_REFERENCE_TITLES]
        if (
            expected
            and sections
            and not sections[0]['content'].strip()
            and unnumbered_chapter(sections[0]['title']) not in expected
            and [unnumbered_chapter(s['title']) for s in remaining] == expected
        ):
            # A standalone bold document title is not a chapter. Remove it only
            # when every remaining chapter exactly satisfies the frozen plan.
            article['sections'] = [{**s, 'id': index} for index, s in enumerate(sections[1:], 1)]
            article['content'] = '\n\n'.join(
                f'**{s["title"]}**\n\n{s["content"]}' for s in article['sections']
            )
        article['qualityIssues'] = validate_confirmed_outline(article['sections'], snapshot)
        return article

    text = normalize_generated_report(content)['content']
    sections = sections_from_markdown(_without_model_references(text))
    request = snapshot.get('request') or {}
    outline = request.get('outline') or snapshot['template'].get('sections', [])
    expected = [unnumbered_chapter(item['title']) for item in outline]
    # Providers may put a subtitle between the document title and the first
    # confirmed chapter. Drop only empty leading headings, never authored prose.
    while sections and not sections[0]['content'].strip() and unnumbered_chapter(sections[0]['title']) not in expected:
        sections = sections[1:]
    if sections and sections[0]['title'] in {'引言', '摘要', '编制说明'} and sections[0]['title'] not in expected:
        sections = sections[1:]
    if not expected or [unnumbered_chapter(section['title']) for section in sections] != expected:
        raise ManuscriptValidationError('文稿检查未通过：填报表正文与确认的章节顺序不一致，请重试')

    chapter_numbers = '一二三四五六七八九十'
    for index, section in enumerate(sections):
        number = chapter_numbers[index] if index < len(chapter_numbers) else str(index + 1)
        section['title'] = f'{number}、{expected[index]}'
    body = '\n\n'.join(f'**{section["title"]}**\n\n{section["content"]}' for section in sections)
    numbered = number_report_citations(
        body, [{'sourceId': str(material['id']), 'type': material.get('type')} for material in materials]
    )
    validate_generated_article(numbered, materials)
    marks = re.compile(r'\[([1-9]\d*)\](?!\()')
    used = {int(value) for value in marks.findall(numbered)}
    cited_materials = [material for index, material in enumerate(materials, 1) if index in used]
    ordinals = {number: index for index, number in enumerate(sorted(used), 1)}
    text = marks.sub(lambda match: f'[{ordinals[int(match[1])]}]', numbered)
    if cited_materials:
        text += '\n\n**参考资料**\n\n' + _bibliography(cited_materials, numbered=True)
    sections = sections_from_markdown(text)
    return {
        'content': text,
        'sections': sections,
        'materials': cited_materials,
        'qualityIssues': validate_confirmed_outline(sections, snapshot),
    }


def validate_confirmed_outline(sections: list[dict], snapshot: dict) -> list[dict]:
    """Enforce frozen chapter identity/order and flag meaningful length deviations.

    Word targets are approximate: Chinese characters and Latin words count as
    units. Grossly short chapters fail; normal drafting variance is an explicit
    warning, never a claim that the requested length was met.
    """
    request = snapshot.get('request') or {}
    outline = request.get('outline') or (snapshot.get('template') or {}).get('sections') or []
    # Historical tasks without an outline retain their existing integrity gate.
    if not outline:
        return []
    expected = [unnumbered_chapter(str(item['title'])) for item in outline]
    chapters = [section for section in sections if section['title'].casefold() not in DELIVERY_REFERENCE_TITLES]
    if chapters and chapters[0]['title'] in {'引言', '摘要', '编制说明'} and chapters[0]['title'] not in expected:
        chapters = chapters[1:]
    actual = [unnumbered_chapter(section['title']) for section in chapters]
    if actual != expected:
        raise ManuscriptValidationError('文稿检查未通过：正文与确认的大纲章节或顺序不一致，请重试生成')
    issues = []
    for section, spec in zip(chapters, outline, strict=True):
        target = spec.get('words')
        if type(target) is not int or target <= 0:
            continue
        prose = re.sub(r'\[[^\]\n]+\](?:\([^\n)]*\))?', '', section['content'])
        actual_words = len(re.findall(r'[\u3400-\u9fff]|[A-Za-z0-9]+(?:[\x27’_-][A-Za-z0-9]+)*', prose))
        if actual_words < min(80, max(10, round(target * 0.15))):
            raise ManuscriptValidationError(
                f'文稿检查未通过：章节“{section["title"]}”正文过短，未满足确认篇幅，请重试生成'
            )
        if not target * 0.65 <= actual_words <= target * 1.5:
            issues.append(
                {
                    'code': 'chapter_length_deviation',
                    'severity': 'warning',
                    'section': section['title'],
                    'message': f'章节“{section["title"]}”约 {actual_words} 字词，规划 {target} 字；请核对篇幅。',
                    'actualWords': actual_words,
                    'targetWords': target,
                }
            )
    return issues


def check_citation_integrity(content: str, materials: list[dict]) -> dict:
    """Map every body occurrence to a frozen source; this does not verify facts."""
    occurrences = []
    unresolved = []
    used = set()
    for section_index, section in enumerate(sections_from_markdown(content)):
        if section['title'].casefold() in DELIVERY_REFERENCE_TITLES:
            continue
        prose = section['content']
        # Preserve offsets while excluding ordinary Markdown links and inline code.
        prose = re.sub(r'\[[^\]\n]*\]\([^\n)]*\)|`[^`\n]*`', lambda match: ' ' * len(match[0]), prose)
        for mark in re.finditer(r'\[([^\]\n]+)\]', prose):
            value = mark[1]
            if not re.fullmatch(r'-?\d+', value):
                if re.search(r'资料\d+|(?:article|paper|file):\d+', value):
                    unresolved.append(value)
                continue
            number = int(value)
            if not 1 <= number <= len(materials):
                unresolved.append(value)
                continue
            start = (
                max(
                    prose.rfind('。', 0, mark.start()),
                    prose.rfind('\n', 0, mark.start()),
                    prose.rfind('！', 0, mark.start()),
                    prose.rfind('？', 0, mark.start()),
                )
                + 1
            )
            ends = [
                pos for punctuation in ('。', '\n', '！', '？') if (pos := prose.find(punctuation, mark.end())) >= 0
            ]
            end = min(ends) + 1 if ends else len(prose)
            source = materials[number - 1]
            used.add(number)
            occurrences.append(
                {
                    'citationId': number,
                    'sourceId': str(source['id']),
                    'type': source.get('type'),
                    'sectionIndex': section_index,
                    'sectionTitle': section['title'],
                    'offset': mark.start(),
                    'quote': section['content'][start:end].strip(),
                }
            )
    unused = [number for number in range(1, len(materials) + 1) if number not in used]
    issues = []
    if unresolved:
        issues.append({'code': 'unresolved_citation', 'message': '存在无法对应来源的引用编号', 'values': unresolved})
    if materials and not occurrences:
        issues.append({'code': 'missing_body_citation', 'message': '正文没有对应所选资料的引用'})
    if unused:
        issues.append({'code': 'unused_sources', 'message': '部分来源未在正文中引用', 'citationIds': unused})
    return {
        'status': 'failed' if unresolved or (materials and not occurrences) else 'warning' if unused else 'passed',
        'scope': 'source_number_and_location',
        'factsVerified': False,
        'occurrences': occurrences,
        'sourceCount': len(materials),
        'usedSourceCount': len(used),
        'issues': issues,
    }
