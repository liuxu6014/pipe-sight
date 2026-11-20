"""The retained Word block styles remain the authority for both export engines."""

from io import BytesIO
from itertools import pairwise

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from pypdf import PdfReader
from test_digest_document import _pagination_report, report

from app.research.services import digest_export
from app.research.services.exporters import build_docx, build_pdf


@pytest.mark.parametrize('kind', ['weekly', 'monthly'])
def test_pdf_resolves_reference_style_indents_and_matches_word_paragraph_spacing(tmp_path, monkeypatch, kind):
    retained_path = digest_export.TEMPLATE_PATH
    original_template = retained_path.read_bytes()
    template = Document(BytesIO(original_template))
    published = next(p for p in template.paragraphs if p.text.strip('{}') == 'published')
    # Use a distinct inherited style to prove this follows the template, not a
    # hard-coded approximation of the accepted 17.85pt reference indentation.
    style = template.styles.add_style('Acceptance block indentation', 1)
    style.base_style = published.style
    style.paragraph_format.left_indent = Pt(23)
    style.paragraph_format.right_indent = Pt(21)
    border = OxmlElement('w:pBdr')
    for side, padding in [('top', 14), ('bottom', 12)]:
        edge = OxmlElement(f'w:{side}')
        edge.set(qn('w:space'), str(padding))
        border.append(edge)
    style._element.get_or_add_pPr().append(border)
    published.style = style
    path = tmp_path / 'reference.docx'
    template.save(path)
    saved_reference = path.read_bytes()
    monkeypatch.setattr(digest_export, 'TEMPLATE_PATH', path)
    captured = []
    original_build = digest_export.SimpleDocTemplate.build

    def capture(self, flowables, *args, **kwargs):
        captured.extend(flowables)
        return original_build(self, flowables, *args, **kwargs)

    monkeypatch.setattr(digest_export.SimpleDocTemplate, 'build', capture)
    value = report(kind)
    document = Document(BytesIO(build_docx(value, is_draft=False)[2]))
    build_pdf(value, is_draft=False)
    paragraphs = [item for item in captured if hasattr(item, 'style')]
    assert len(document.paragraphs) == len(paragraphs)
    for index, (word, pdf) in enumerate(zip(document.paragraphs, paragraphs, strict=True)):
        assert pdf.style.spaceBefore == word.paragraph_format.space_before.pt
        assert pdf.style.spaceAfter == word.paragraph_format.space_after.pt
        assert pdf.style.leading == word.paragraph_format.line_spacing.pt
        if word.text.startswith('发布时间：'):
            assert pdf.style.leftIndent == 23
            assert pdf.style.rightIndent == 21
            assert (pdf.top, pdf.bottom) == (14, 12)
        elif word.text.startswith(('行业洞察：', '数据源：', '[')):
            assert pdf.style.leftIndent == 17.85
            assert pdf.style.rightIndent == 17.85
            if word.text.startswith('行业洞察：'):
                assert (pdf.top, pdf.bottom) == (10, 10)
            elif word.text == '数据源：':
                assert (pdf.top, pdf.bottom) == (10, 0)
            else:
                next_is_source = index + 1 < len(document.paragraphs) and document.paragraphs[
                    index + 1
                ].text.startswith('[')
                assert (pdf.top, pdf.bottom) == (0, 0 if next_is_source else 10)
    assert path.read_bytes() == saved_reference
    assert retained_path.read_bytes() == original_template


@pytest.mark.parametrize('kind', ['weekly', 'monthly'])
def test_pdf_reference_gutters_and_vertical_group_geometry(kind):
    value = report(kind)
    value.content = (
        '**短类别**\n\n### 1. 短标题\n\n正文只有一行。\n\n发布时间：2026-10-21'
        '\n\n行业洞察：需要试验验证。\n\n数据源：'
        '\n\n[1] [第一条来源](https://example.org/a)\n\n[2] [第二条来源](https://example.org/b)'
    )
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    assert len(pdf.pages) == 1
    positions = {}

    def locate(text, canvas, matrix, _font, size):
        if text.strip():
            positions[text.strip()] = (
                matrix[4] * canvas[0] + matrix[5] * canvas[2] + canvas[4],
                matrix[4] * canvas[1] + matrix[5] * canvas[3] + canvas[5],
                size,
            )

    pdf.pages[0].extract_text(visitor_text=locate)
    assert abs(positions['一、短类别'][0] - 90) < 0.01  # Compensate the PDF Frame's 6pt padding.
    assert abs(positions['正文只有一行。'][0] - 114) < 0.01  # Two CJK characters at 12pt.
    metadata = ['发布时间：2026-10-21', '行业洞察：需要试验验证。', '数据源：', '[1] 第一条来源', '[2] 第二条来源']
    for text in metadata:
        assert abs(positions[text][0] - 107.85) < 0.01  # Reference Word 17.85pt block gutters.
        assert positions[text][2] == 12
    # Reserve each Word border group's 10pt top/bottom inset. Adjacent blue
    # source paragraphs share one group, so links must not repeat that inset.
    gaps = [positions[first][1] - positions[second][1] for first, second in pairwise(metadata)]
    assert all(abs(actual - expected) < 0.01 for actual, expected in zip(gaps, [42, 42, 22, 22], strict=True))


def test_oversized_single_insight_splits_without_losing_text_or_source_links():
    value = report()
    sentence = '超长洞察仍需保留完整证据。'
    value.content = value.content.replace('应用条件仍需结合现场试验核实。', sentence * 200)
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    assert len(pdf.pages) > 1
    text = ''.join(''.join(page.extract_text().split()) for page in pdf.pages)
    assert text.count(sentence) == 200
    links = [item.get_object()['/A']['/URI'] for page in pdf.pages for item in page.get('/Annots', [])]
    assert set(links) == {'https://example.org/news', 'https://doi.org/10.0000/example'}


def _page_texts(value):
    return [
        ''.join(page.extract_text().split()) for page in PdfReader(BytesIO(build_pdf(value, is_draft=False)[2])).pages
    ]


def test_long_body_uses_remaining_page_below_previous_metadata():
    value = _pagination_report(35)
    title = '长段落应该利用当前页剩余空间'
    body = '续写正文应在元数据后继续，保持标题与开头两行同页。' * 40
    value.content += f'\n\n### 2. {title}\n\n{body}'
    pages = _page_texts(value)
    metadata_page = next(index for index, text in enumerate(pages) if '[4]第4条来源标题：' in text)
    assert title in pages[metadata_page]
    assert body[:55] in pages[metadata_page]  # More than one full CJK line at the reference text width.
    assert body in ''.join(pages)
    assert any('续写正文应在元数据后继续' in text for text in pages[metadata_page + 1 :])


@pytest.mark.parametrize('paragraphs', ['long', 'multiple', 'short'])
def test_wrapped_heading_stays_with_initial_body_lines(paragraphs):
    value = _pagination_report(15)
    title = '换行后的长标题也必须完整连接正文开头' * 8
    if paragraphs == 'multiple':
        body = '短首段。\n\n' + '第二段正文必须保留开头两行并完整保存所有文字。' * 40
        prefix = '短首段。' + ('第二段正文必须保留开头两行并完整保存所有文字。' * 3)[:55]
    elif paragraphs == 'short':
        body = prefix = '正文只有简短的一行。'
    else:
        body = '正文前两行必须与长标题保持相邻而不是把整段推走。' * 40
        prefix = body[:55]
    value.content += f'\n\n### 2. {title}\n\n{body}'
    pages = _page_texts(value)
    heading_page = next(index for index, text in enumerate(pages) if title in text)
    assert prefix in pages[heading_page]
    assert ''.join(body.split()) in ''.join(pages)


def test_heading_without_summary_stays_with_following_metadata():
    value = _pagination_report(15)
    title = '缺少正文时仍连接后续资料信息'
    value.content += (
        f'\n\n### 2. {title}\n\n发布时间：2026-10-22\n\n行业洞察：仍需补充证据。'
        '\n\n数据源：\n\n[5] [第二项来源](https://example.org/source/5)'
    )
    pages = _page_texts(value)
    heading_page = next(index for index, text in enumerate(pages) if title in text)
    assert '发布时间：2026-10-22' in pages[heading_page]
    assert '[5]第二项来源' in pages[heading_page]
