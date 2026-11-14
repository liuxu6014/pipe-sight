"""从保留的简报样例模板排版；不把研究报告版式套到周报月报。"""

import re
from collections.abc import Iterator
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.research.services.digest_document import digest_masthead, digest_period

TEMPLATE_PATH = Path(__file__).resolve().parents[4] / 'data/templates/digest-reference-v1.docx'
LINK = re.compile(r'^\[(\d+)\] \[(.+)\]\((https?://[^\s]+)\)$')
FONT_SIZES = {'title': 18, 'period': 16, 'category': 16, 'event': 14}


def _chinese(number) -> str:
    digits = '零一二三四五六七八九'
    return (
        digits[number]
        if number < 10  # noqa: PLR2004
        else (digits[number // 10] if number >= 20 else '')  # noqa: PLR2004
        + '十'
        + (digits[number % 10] if number % 10 else '')
    )


def digest_blocks(content) -> Iterator[tuple[str, str]]:
    """Stable semantic roles shared by the Word and PDF exporters."""
    category_index = 0
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('**') and line.endswith('**'):
            category_index += 1
            yield 'category', f'{_chinese(category_index)}、{line[2:-2]}'
        elif line.startswith('### '):
            yield 'event', line[4:]
        elif line.startswith('发布时间：'):
            yield 'published', line
        elif line.startswith('行业洞察：'):
            yield 'insight', line
        elif line == '数据源：':
            yield 'source_label', line
        elif re.match(r'^\[\d+\] ', line):
            yield 'source', line
        else:
            yield 'summary', line


def _text(paragraph, value, *, bold=False, underline=False) -> Any:
    # Keep the reference's run typography, not python-docx's default Calibri.
    original = paragraph.runs[0]._r.rPr if paragraph.runs else None
    for node in list(paragraph._p):
        if node.tag != qn('w:pPr'):
            paragraph._p.remove(node)
    run = paragraph.add_run(value)
    if original is not None:
        run._r.insert(0, deepcopy(original))
    if bold:
        run.bold = True
    if underline:
        run.underline = True
    return run


def _hyperlink(paragraph, number, label, url) -> None:
    _text(paragraph, f'[{number}] ')
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(
        qn('r:id'),
        paragraph.part.relate_to(
            url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True
        ),
    )
    run = OxmlElement('w:r')
    props = deepcopy(paragraph.runs[0]._r.rPr)
    for tag, value in [('color', '0000FF'), ('u', 'single')]:
        old = props.find(qn(f'w:{tag}'))
        if old is not None:
            props.remove(old)
        node = OxmlElement(f'w:{tag}')
        node.set(qn('w:val'), value)
        props.append(node)
    run.append(props)
    text = OxmlElement('w:t')
    text.text = label
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def build_digest_docx(report) -> bytes:
    document = Document(TEMPLATE_PATH)
    prototypes = {p.text.strip('{}'): deepcopy(p._p) for p in document.paragraphs}
    body = document._element.body
    for child in list(body):
        if child.tag != qn('w:sectPr'):
            body.remove(child)

    def add(role, value) -> Any:
        from docx.text.paragraph import Paragraph as WordParagraph  # noqa: PLC0415

        element = deepcopy(prototypes[role])
        body.insert(len(body) - 1, element)
        paragraph = WordParagraph(element, document._body)
        _text(paragraph, value)
        size = FONT_SIZES.get(role, 12)
        paragraph.runs[0].font.size = Pt(size)
        # The retained paragraph mark and complex-script size also affect line
        # height in Word/LibreOffice, even when the visible run is smaller.
        properties = element.get_or_add_pPr()
        for props in (properties.find(qn('w:rPr')), paragraph.runs[0]._r.get_or_add_rPr()):
            if props is not None:
                for tag in ('sz', 'szCs'):
                    node = props.find(qn(f'w:{tag}'))
                    if node is None:
                        node = OxmlElement(f'w:{tag}')
                        props.append(node)
                    node.set(qn('w:val'), str(size * 2))
        snap = properties.find(qn('w:snapToGrid'))
        if snap is None:
            snap = OxmlElement('w:snapToGrid')
            properties.append(snap)
        snap.set(qn('w:val'), '0')
        paragraph.paragraph_format.line_spacing = 1.45
        paragraph.paragraph_format.space_before = Pt(8 if role in {'category', 'event'} else 3)
        paragraph.paragraph_format.space_after = Pt(4)
        spacing = properties.find(qn('w:spacing'))
        for attr in ('beforeLines', 'afterLines'):
            spacing.set(qn(f'w:{attr}'), '0')
        paragraph.paragraph_format.widow_control = True
        # Render numbers as text to avoid Word/LibreOffice list-state drift.
        if role in {'category', 'event'}:
            num = element.get_or_add_pPr().get_or_add_numPr()
            num.get_or_add_numId().val = 0
            paragraph.paragraph_format.keep_with_next = True
        if role in {'published', 'insight', 'source_label', 'source'}:
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.35
        if role in {'published', 'insight'}:
            label, text = value.split('：', 1)
            _text(paragraph, label + '：', bold=True, underline=role == 'insight')
            extra = paragraph.add_run(text)
            extra._r.insert(0, deepcopy(paragraph.runs[0]._r.rPr))
            extra.bold = False
            extra.underline = False
        if role in {'insight', 'source_label'}:
            paragraph.paragraph_format.keep_with_next = True
        if role == 'source_label':
            paragraph.runs[0].bold = True
        if role == 'source' and (match := LINK.fullmatch(value)):
            _hyperlink(paragraph, *match.groups())
        return paragraph

    title = str(report.title)
    document.core_properties.title = title
    metadata = getattr(report, 'metadata', {})
    add('title', digest_masthead(title, metadata))
    period = add('period', digest_period(metadata))
    period_properties = period._p.get_or_add_pPr()
    auto_space_numbers = OxmlElement('w:autoSpaceDN')
    auto_space_numbers.set(qn('w:val'), '0')
    period_properties.insert_element_before(auto_space_numbers, 'w:snapToGrid', 'w:spacing', 'w:jc', 'w:rPr')
    border = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    for key, val in [('val', 'single'), ('sz', '24'), ('space', '12'), ('color', 'FF0000')]:
        bottom.set(qn(f'w:{key}'), val)
    border.append(bottom)
    period_properties.append(border)
    for role, text in digest_blocks(report.content):
        add(role, text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _digest_pdf_font(text: str, fallback: str) -> str:
    name = 'PipeSightDigestFangSong'
    if name not in pdfmetrics.getRegisteredFontNames():
        for path in (
            Path.home() / 'Library/Fonts/仿宋_GB2312.ttf',
            Path('/Library/Fonts/FangSong_GB2312.ttf'),
            Path('/usr/local/share/fonts/FangSong_GB2312.ttf'),
            Path('C:/Windows/Fonts/simfang.ttf'),
        ):
            if not path.is_file():
                continue
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)
            except TTFError:
                continue
            break
        else:
            return fallback
    glyphs = pdfmetrics.getFont(name).face.charToGlyph
    return name if all(glyphs.get(ord(char)) for char in set(text) if not char.isspace()) else fallback


def build_digest_pdf(report, font_name) -> bytes:
    metadata = getattr(report, 'metadata', {})
    title = digest_masthead(str(report.title), metadata)
    period = digest_period(metadata)
    blocks = list(digest_blocks(report.content))
    font_name = _digest_pdf_font(title + period + ''.join(text for _, text in blocks), font_name)
    base = {
        'fontName': font_name,
        'wordWrap': 'CJK',
        'fontSize': 12,
        'leading': 18,
        'spaceBefore': 5,
        'spaceAfter': 5,
    }
    styles = {
        'title': ParagraphStyle(
            'DigestTitle',
            **{
                **base,
                'fontSize': FONT_SIZES['title'],
                'leading': 26,
                'textColor': HexColor('#FF0000'),
                'alignment': TA_CENTER,
            },
        ),
        'period': ParagraphStyle(
            'DigestPeriod',
            **{**base, 'fontSize': FONT_SIZES['period'], 'leading': 23, 'alignment': TA_CENTER, 'spaceAfter': 12},
        ),
        'category': ParagraphStyle(
            'DigestCategory', **{**base, 'fontSize': FONT_SIZES['category'], 'leading': 26, 'keepWithNext': True}
        ),
        'event': ParagraphStyle(
            'DigestEvent', **{**base, 'fontSize': FONT_SIZES['event'], 'leading': 22, 'keepWithNext': True}
        ),
        'summary': ParagraphStyle('DigestSummary', **base, firstLineIndent=24),
    }
    for role, fill in [
        ('published', '#F8FBF6'),
        ('insight', '#FEFCF2'),
        ('source_label', '#F6F8FC'),
        ('source', '#F6F8FC'),
    ]:
        styles[role] = ParagraphStyle(
            f'Digest{role}',
            **base,
            backColor=HexColor(fill),
            borderPadding=5,
            keepWithNext=role in {'insight', 'source_label'},
        )
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        # SimpleDocTemplate adds six points of frame padding on each side.
        leftMargin=31.75 * mm - 6,
        rightMargin=31.75 * mm - 6,
        topMargin=25.4 * mm,
        bottomMargin=25.4 * mm,
        title=str(report.title),
    )
    story = [
        Paragraph(escape(title), styles['title']),
        Paragraph(escape(period), styles['period']),
    ]
    from reportlab.platypus import HRFlowable  # noqa: PLC0415

    story.extend([HRFlowable(width='100%', thickness=3, color=HexColor('#FF0000')), Spacer(1, 12)])
    for role, text in blocks:
        markup = escape(text)
        if role == 'source' and (match := LINK.fullmatch(text)):
            number, label, url = match.groups()
            markup = (
                f'[{number}] <link href="{escape(url, {chr(34): "&quot;"})}" color="blue"><u>{escape(label)}</u></link>'
            )
        elif role in {'published', 'insight'}:
            label, value = markup.split('：', 1)
            markup = f'<b><u>{label}：</u></b>{value}' if role == 'insight' else f'<b>{label}：</b>{value}'
        story.append(Paragraph(markup, styles[role]))
    doc.build(story)
    return output.getvalue()
