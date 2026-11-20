"""从保留的简报样例模板排版；不把研究报告版式套到周报月报。"""

import os
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
from reportlab.platypus import CondPageBreak, Flowable, Paragraph, SimpleDocTemplate, Spacer

from app.research.services.digest_document import clean_source_display, digest_masthead, digest_period
from app.research.services.pdf_fonts import CJK_REQUIRED_TEXT, register_configured_font

TEMPLATE_PATH = Path(__file__).resolve().parents[4] / 'data/templates/digest-reference-v1.docx'
LINK = re.compile(r'^\[(\d+)\] \[(.+)\]\((https?://[^\s]+)\)$')
FONT_SIZES = {'title': 18, 'period': 16, 'category': 16, 'event': 14}
LINE_HEIGHTS = {'title': 26, 'period': 23, 'category': 26, 'event': 22}
FRAME_PADDING = 6


def _paragraph_spacing(role: str) -> tuple[int, int]:
    """The accepted compact Word sizing applies to both export engines."""
    return (8 if role in {'category', 'event'} else 3), 4


def _reference_block_layout() -> dict[str, dict[str, float]]:
    """Resolve inherited reference styles instead of losing their block gutters."""
    result = {}
    for paragraph in Document(TEMPLATE_PATH).paragraphs:
        role = paragraph.text.strip('{}')
        if role not in {'published', 'insight', 'source_label', 'source'}:
            continue
        values = []
        for attribute in ('left_indent', 'right_indent'):
            value = getattr(paragraph.paragraph_format, attribute)
            style = paragraph.style
            while value is None and style is not None:
                value = getattr(style.paragraph_format, attribute)
                style = style.base_style
            values.append(value.pt if value is not None else 0)
        layout = dict(zip(('left_indent', 'right_indent'), values, strict=True))
        property_sources = [paragraph._p.pPr]
        style = paragraph.style
        while style is not None:
            property_sources.append(style._element.pPr)
            style = style.base_style
        for side in ('top', 'right', 'bottom', 'left'):
            padding = 0
            for properties in property_sources:
                border = properties.find(qn('w:pBdr')) if properties is not None else None
                edge = border.find(qn(f'w:{side}')) if border is not None else None
                if edge is not None and edge.get(qn('w:space')) is not None:
                    padding = float(edge.get(qn('w:space')))
                    break
            layout['padding_' + side] = padding
        result[role] = layout
    return result


class DigestBlockParagraph(Flowable):
    """Reserve Word border spacing; Paragraph borderPadding only paints it."""

    def __init__(self, paragraph: Paragraph, *, top: float, bottom: float) -> None:
        super().__init__()
        self.paragraph, self.style = paragraph, paragraph.style
        self.top, self.bottom = top, bottom

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        width, height = self.paragraph.wrap(available_width, max(0, available_height - self.top - self.bottom))
        self.width, self.height = width, height + self.top + self.bottom
        return self.width, self.height

    def draw(self) -> None:
        self.paragraph.drawOn(self.canv, 0, self.bottom)

    def split(self, available_width: float, available_height: float) -> list[Flowable]:
        pieces = self.paragraph.split(available_width, max(0, available_height - self.top - self.bottom))
        result = []
        for index, paragraph in enumerate(pieces):
            item = DigestBlockParagraph(
                paragraph,
                top=self.top if index == 0 else 0,
                bottom=self.bottom if index == len(pieces) - 1 else 0,
            )
            item.keepWithNext = True if index < len(pieces) - 1 else self.getKeepWithNext()
            result.append(item)
        return result


def _heading_start_height(blocks: list[tuple[str, str]], index: int, styles: dict, width: float) -> float | None:
    """Keep wrapped headings with initial body lines, without pinning a long body."""
    height = 0
    while index < len(blocks) and blocks[index][0] in {'category', 'event'}:
        role, text = blocks[index]
        paragraph = Paragraph(escape(text), styles[role])
        height += paragraph.wrap(width, 1e6)[1] + paragraph.getSpaceBefore() + paragraph.getSpaceAfter()
        index += 1
    required_lines = 2
    found_body = False
    while index < len(blocks) and blocks[index][0] == 'summary' and required_lines > 0:
        paragraph = Paragraph(escape(blocks[index][1]), styles['summary'])
        paragraph.wrap(width, 1e6)
        lines = len(paragraph.blPara.lines)
        # A three-line paragraph cannot split into two orphan/widow-free parts.
        # Short initial paragraphs stay whole before considering the next one.
        kept_lines = lines if lines <= 3 else 2  # noqa: PLR2004
        height += kept_lines * paragraph.style.leading + paragraph.getSpaceBefore() + paragraph.getSpaceAfter()
        required_lines -= kept_lines
        found_body = found_body or bool(lines)
        index += 1
    return height if found_body else None


class DigestHeadingParagraph(Paragraph):
    """Match Word's synthetic bold when the installed FangSong has one face."""

    def draw(self) -> None:
        self.canv.saveState()
        self.canv.setStrokeColor(self.style.textColor)
        self.canv.setLineWidth(0.22)
        self.canv.addLiteral('2 Tr')  # Fill and stroke, without drawing the text twice.
        try:
            super().draw()
        finally:
            self.canv.addLiteral('0 Tr')
            self.canv.restoreState()


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
            # Saved historical Markdown can contain old provenance notes. Clean
            # just its visible label for both exporters; never rewrite its URL.
            match = LINK.fullmatch(line)
            if match:
                number, label, url = match.groups()
                line = f'[{number}] [{clean_source_display(label)}]({url})'
            else:
                line = clean_source_display(line)
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
        # Multiple spacing depends on the font's metrics and can inflate Word
        # output compared with PDF. Use the same point-based leading in both.
        paragraph.paragraph_format.line_spacing = Pt(LINE_HEIGHTS.get(role, 18))
        before, after = _paragraph_spacing(role)
        paragraph.paragraph_format.space_before = Pt(before)
        paragraph.paragraph_format.space_after = Pt(after)
        spacing = properties.find(qn('w:spacing'))
        for attr in ('beforeLines', 'afterLines'):
            spacing.set(qn(f'w:{attr}'), '0')
        paragraph.paragraph_format.widow_control = True
        if role in {'category', 'event', 'published', 'insight', 'source_label', 'source'}:
            paragraph.paragraph_format.keep_together = True
        # Render numbers as text to avoid Word/LibreOffice list-state drift.
        if role in {'category', 'event'}:
            num = element.get_or_add_pPr().get_or_add_numPr()
            num.get_or_add_numId().val = 0
            paragraph.paragraph_format.keep_with_next = True
        if role in {'published', 'insight', 'source_label', 'source'}:
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.line_spacing = Pt(18)
        if role in {'published', 'insight'}:
            label, text = value.split('：', 1)
            _text(paragraph, label + '：', bold=True, underline=role == 'insight')
            extra = paragraph.add_run(text)
            extra._r.insert(0, deepcopy(paragraph.runs[0]._r.rPr))
            extra.bold = False
            extra.underline = False
        if role in {'published', 'insight', 'source_label'}:
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
    blocks = list(digest_blocks(report.content))
    for index, (role, text) in enumerate(blocks):
        paragraph = add(role, text)
        if role == 'source':
            # Keep all of this event's sources with its insight, not only the
            # first link. Stop the chain before the next event/category.
            paragraph.paragraph_format.keep_with_next = index + 1 < len(blocks) and blocks[index + 1][0] == 'source'
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _digest_pdf_font(text: str, fallback: str) -> str:
    configured = os.getenv('PDF_DIGEST_FONT_PATH', '').strip()
    if configured:
        return register_configured_font(
            configured,
            prefix='PipeSightDigestExplicit',
            label='PDF_DIGEST_FONT_PATH',
            required_text=CJK_REQUIRED_TEXT + text,
        )
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
        'spaceBefore': _paragraph_spacing('summary')[0],
        'spaceAfter': _paragraph_spacing('summary')[1],
        'allowOrphans': False,
        'allowWidows': False,
    }
    styles = {
        'title': ParagraphStyle(
            'DigestTitle',
            **{
                **base,
                'fontSize': FONT_SIZES['title'],
                'leading': LINE_HEIGHTS['title'],
                'textColor': HexColor('#FF0000'),
                'alignment': TA_CENTER,
            },
        ),
        'period': ParagraphStyle(
            'DigestPeriod',
            **{
                **base,
                'fontSize': FONT_SIZES['period'],
                'leading': LINE_HEIGHTS['period'],
                'alignment': TA_CENTER,
            },
        ),
        'category': ParagraphStyle(
            'DigestCategory',
            **{
                **base,
                'fontSize': FONT_SIZES['category'],
                'leading': LINE_HEIGHTS['category'],
                'spaceBefore': _paragraph_spacing('category')[0],
                'keepWithNext': True,
            },
        ),
        'event': ParagraphStyle(
            'DigestEvent',
            **{
                **base,
                'fontSize': FONT_SIZES['event'],
                'leading': LINE_HEIGHTS['event'],
                'spaceBefore': _paragraph_spacing('event')[0],
                'keepWithNext': True,
            },
        ),
        'summary': ParagraphStyle('DigestSummary', **base, firstLineIndent=24),
    }
    reference_layout = _reference_block_layout()
    fills = {'published': '#F8FBF6', 'insight': '#FEFCF2', 'source_label': '#F6F8FC', 'source': '#F6F8FC'}
    for role, fill in fills.items():
        styles[role] = ParagraphStyle(
            f'Digest{role}',
            **base,
            leftIndent=reference_layout[role]['left_indent'],
            rightIndent=reference_layout[role]['right_indent'],
            backColor=HexColor(fill),
            borderPadding=5,
            keepWithNext=role in {'published', 'insight', 'source_label'},
        )
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        # SimpleDocTemplate adds six points of frame padding on each side.
        leftMargin=31.75 * mm - FRAME_PADDING,
        rightMargin=31.75 * mm - FRAME_PADDING,
        topMargin=25.4 * mm,
        bottomMargin=25.4 * mm,
        title=str(report.title),
    )
    story = [
        DigestHeadingParagraph(escape(title), styles['title']),
        DigestHeadingParagraph(escape(period), styles['period']),
    ]
    from reportlab.platypus import HRFlowable  # noqa: PLC0415

    story.extend([HRFlowable(width='100%', thickness=3, color=HexColor('#FF0000')), Spacer(1, 12)])
    for index, (role, text) in enumerate(blocks):
        markup = escape(text)
        if role == 'source' and (match := LINK.fullmatch(text)):
            number, label, url = match.groups()
            markup = (
                f'[{number}] <link href="{escape(url, {chr(34): "&quot;"})}" color="blue"><u>{escape(label)}</u></link>'
            )
        elif role in {'published', 'insight'}:
            label, value = markup.split('：', 1)
            markup = f'<b><u>{label}：</u></b>{value}' if role == 'insight' else f'<b>{label}：</b>{value}'
        paragraph_type = DigestHeadingParagraph if role in {'category', 'event', 'source_label'} else Paragraph
        if role in fills:
            layout = reference_layout[role]
            previous_fill = fills.get(blocks[index - 1][0]) if index else None
            next_fill = fills.get(blocks[index + 1][0]) if index + 1 < len(blocks) else None
            # Adjacent blue source paragraphs form one Word border group. Its
            # vertical inset belongs at the group's ends, not around every link.
            top = layout['padding_top'] if previous_fill != fills[role] else 0
            bottom = layout['padding_bottom'] if next_fill != fills[role] else 0
            style = ParagraphStyle(
                f'DigestBlock{index}',
                parent=styles[role],
                borderPadding=(top or 5, layout['padding_right'], bottom or 5, layout['padding_left']),
            )
            paragraph = DigestBlockParagraph(paragraph_type(markup, style), top=top, bottom=bottom)
        else:
            paragraph = paragraph_type(markup, styles[role])
        if role in {'category', 'event'}:
            height = _heading_start_height(blocks, index, styles, doc.width - 2 * FRAME_PADDING)
            if height is not None and height <= doc.height - 2 * FRAME_PADDING:
                story.append(CondPageBreak(height))
                # Word keeps headings with the beginning of the next paragraph,
                # not its entire long body. The measured guard preserves that
                # minimum while allowing the body to use the remaining page.
                paragraph.keepWithNext = False
        if role == 'source':
            paragraph.keepWithNext = index + 1 < len(blocks) and blocks[index + 1][0] == 'source'
        story.append(paragraph)
    doc.build(story)
    return output.getvalue()
