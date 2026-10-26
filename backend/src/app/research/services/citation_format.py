"""Canonical report citations, shared by persistence and portable exporters."""

import re

REFERENCE_TITLES = frozenset({'参考资料', '参考文献', 'references'})


def clean_report_citations(content: str, title: str = '') -> str:
    if title.strip().casefold() in REFERENCE_TITLES:
        return content
    def sentence(match: re.Match[str]) -> str:
        clause = match.group(0)
        markers = list(dict.fromkeys(re.findall(r'\[[1-9]\d*\](?!\()', clause)))
        if not markers:
            return clause
        def group(match: re.Match[str]) -> str:
            # Drop citation-list joiners, never a connective between prose claims.
            if not clause[:match.start()].strip() or re.match(r'^[ \t]*(?:[，,：:]|$)', clause[match.end():]):
                return ''.join(re.findall(r'\[[1-9]\d*\]', match[0]))
            return match[0]

        joined = re.sub(r'\[[1-9]\d*\](?:(?:和|及|与|、)\[[1-9]\d*\])+', group, clause)
        body = re.sub(r'\[[1-9]\d*\](?!\()', '', joined)
        return body.rstrip(' \t') + ''.join(markers) + body[len(body.rstrip(' \t')):]

    lines, reference_level, fence = [], None, None
    for line in content.split('\n'):
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
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', line)
        if heading:
            level, name = len(heading[1]), heading[2].strip().casefold()
            if reference_level is not None and level <= reference_level:
                reference_level = None
            if name in REFERENCE_TITLES:
                reference_level = level
            lines.append(line)
            continue
        if reference_level is not None:
            lines.append(line)
            continue
        # Markdown links and literal code are not evidence markers.
        protected = []

        def protect(match: re.Match[str]) -> str:
            protected.append(match.group(0))
            return f'\ue000{len(protected) - 1}\ue001'

        text = re.sub(r'`+[^`\n]*`+', protect, line)
        text = re.sub(r'(\[\d+\])[ \t]*[（(](?:新闻正文|论文摘要|文献信息|用户资料|内部资料)[^()（）\n]*[）)]', r'\1', text)
        text = re.sub(r'\[[^\]\n]*\]\([^\n)]*\)', protect, text)
        text = re.sub(r'[^。！？；\n]+', sentence, text)
        lines.append(re.sub(r'\ue000(\d+)\ue001', lambda match: protected[int(match[1])], text))

    return '\n'.join(lines)
