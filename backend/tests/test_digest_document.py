"""简报样例格式与真实选材来源的契约。"""

import json
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from pypdf import PdfReader

from app.research.services.digest_document import DIGEST_FORMAT, digest_period, normalize_digest_document
from app.research.services.exporters import build_docx, build_pdf
from app.research.services.report_content import normalize_generated_report, validate_generated_article


def materials() -> list:
    return [
        {
            'id': '20',
            'type': 'article',
            'title': '检测技术公开报道',
            'source': {'name': '国家管网', 'url': 'https://example.org/news', 'published_at': '2026-10-21T02:00:00Z'},
        },
        {
            'id': '20',
            'type': 'paper',
            'title': '检测方法研究',
            'source': {'journal': '研究期刊', 'doi': '10.0000/example'},
        },
    ]


def document() -> dict:
    return {
        'format': DIGEST_FORMAT,
        'groups': [
            {
                'category': '油气管网',
                'items': [
                    {
                        'title': '检测技术验证进展',
                        'summary': '报道介绍了检测方法的现场试用情况。',
                        'insight': '应用条件仍需结合现场试验核实。',
                        'sourceIds': ['article:20', 'paper:20'],
                    },
                    {
                        'title': '检测方法的研究边界',
                        'summary': '论文讨论检测方法及其局限。',
                        'insight': '尚需补充长期运行数据，不能据摘要推断检测性能。',
                        'sourceIds': ['paper:20'],
                    },
                ],
            }
        ],
    }


def report(kind='weekly') -> SimpleNamespace:
    result = normalize_digest_document(json.dumps(document(), ensure_ascii=False), materials())
    return SimpleNamespace(
        title='管网科技情报' + ('周报' if kind == 'weekly' else '月报'),
        report_type=kind,
        content=result['content'],
        sections=result['sections'],
        metadata={'period': ['2026-10-19', '2026-10-25'] if kind == 'weekly' else ['2026-10-01', '2026-10-31']},
        citations=[],
    )


def test_digest_groups_entries_and_builds_sources_from_frozen_materials() -> None:
    raw = json.dumps(document(), ensure_ascii=False)
    result = normalize_digest_document(raw, materials())
    text = result['content']
    assert (
        text.index('### 1.')
        < text.index('发布时间：')
        < text.index('行业洞察：')
        < text.index('数据源：')
        < text.index('### 2.')
    )
    assert '[1] [检测技术公开报道【国家管网】](https://example.org/news)' in text
    assert '[2] [检测方法研究【研究期刊】](https://doi.org/10.0000/example)' in text
    assert text.count('发布时间：') == 1
    assert 'article:20' not in text and '参考资料' not in text
    assert normalize_generated_report(text)['content'] == text
    assert normalize_generated_report(raw, materials()) == result
    validate_generated_article(text, materials())


@pytest.mark.parametrize('publisher', ['新华网（国家管网官网转载）', '新华网(官网核验微信来源)', '新华网（尚未核实）'])
def test_digest_sources_hide_editorial_notes_without_changing_frozen_evidence(publisher) -> None:
    selected = materials()
    selected[0]['source']['name'] = publisher
    original = deepcopy(selected)
    text = normalize_digest_document(json.dumps(document()), selected)['content']
    assert '[检测技术公开报道【新华网】](https://example.org/news)' in text
    assert publisher not in text
    assert selected == original


@pytest.mark.parametrize('change', ['source', 'summary', 'insight', 'groups', 'markup'])
def test_invalid_digest_is_not_accepted_as_a_finished_report(change) -> None:
    data = document()
    item = data['groups'][0]['items'][0]
    if change == 'source':
        item['sourceIds'] = ['file:20']
    elif change == 'groups':
        data['groups'] = []
    elif change == 'markup':
        item['summary'] = '<script>invalid</script>'
    else:
        item[change] = ''
    with pytest.raises(ValueError):
        normalize_digest_document(json.dumps(data), materials())


def test_digest_period_includes_the_end_year_when_the_range_crosses_new_year() -> None:
    assert digest_period({'period': ['2025-12-29', '2026-01-04']}) == '2025年12月29日到2026年1月4日'
    assert digest_period({'period': ['2026-01-04', '2026-01-04']}) == '2026年1月4日'


def test_new_digest_rejects_splitting_one_source_into_multiple_events() -> None:
    data = document()
    for item in data['groups'][0]['items']:
        item['sourceIds'] = ['article:20']
    with pytest.raises(ValueError, match='重复拆条'):
        normalize_digest_document(json.dumps(data), materials()[:1], generation_options={})


def test_digest_rejects_omitting_a_category_with_matched_sources() -> None:
    data = document()
    data['groups'][0]['items'].pop()
    screening = {
        'categories': [{'name': '工程验证'}, {'name': '学术研究'}],
        'labels': {
            'article:20': {'keep': True, 'category': '工程验证'},
            'paper:20': {'keep': True, 'category': '学术研究'},
        },
    }
    with pytest.raises(ValueError, match='缺少有通过资料的类别“学术研究”'):
        normalize_digest_document(json.dumps(data), materials(), screening=screening)


def test_new_digest_enforces_the_selected_summary_and_category_limits() -> None:
    data = document()
    assert normalize_digest_document(json.dumps(data), materials(), generation_options={'itemCount': 2})
    with pytest.raises(ValueError, match='事件数量'):
        normalize_digest_document(json.dumps(data), materials(), generation_options={'itemCount': 1})
    data['groups'][0]['items'][0]['summary'] = '摘要' * 61
    with pytest.raises(ValueError, match='120 字'):
        normalize_digest_document(json.dumps(data), materials(), generation_options={'summaryLength': 'short'})


def test_generated_monthly_masthead_and_sources_fit_together() -> None:
    data = document()
    item = data['groups'][0]['items'][0]
    item['title'] = '超大口径管道内检测装备与长输管网在线仿真系统首次亮相'
    item['summary'] = '会议展示管道检测装备。' * 16
    item['insight'] = '需核实不同工况的检测性能和工程应用。' * 8
    data['groups'][0]['items'] = [item]
    value = report('monthly')
    value.title += ' 2026年10月'
    value.content = normalize_digest_document(json.dumps(data), materials())['content']
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    assert len(pdf.pages) == 1
    text = pdf.pages[0].extract_text()
    assert text.splitlines()[0].strip() == '科技情报月报'
    assert '2026年10月1日到10月31日' in text
    assert '数据源：' in text


def test_export_saved_digest_cleans_source_labels_but_never_changes_markdown_or_urls() -> None:
    value = report()
    url = 'https://example.org/官网转载?original=1'
    value.content = value.content.replace(
        '[检测技术公开报道【国家管网】](https://example.org/news)',
        f'[检测技术公开报道【新华网（国家管网官网转载）】]({url})',
    )
    original = value.content
    word = build_docx(value, is_draft=False)[2]
    with ZipFile(BytesIO(word)) as archive:
        xml = archive.read('word/document.xml').decode()
        rels = archive.read('word/_rels/document.xml.rels').decode()
    assert '检测技术公开报道【新华网】' in xml
    assert '国家管网官网转载' not in xml
    assert url in rels
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    text = ''.join(page.extract_text() for page in pdf.pages)
    assert '检测技术公开报道【新华网】' in text
    assert '国家管网官网转载' not in text
    links = [
        annotation.get_object().get('/A', {}).get('/URI')
        for page in pdf.pages
        for annotation in page.get('/Annots', [])
    ]
    assert url in links
    assert value.content == original


@pytest.mark.parametrize('kind', ['weekly', 'monthly'])
def test_word_and_pdf_follow_reference_layout_and_preserve_per_event_sources(kind) -> None:
    value = report(kind)
    _, _, data = build_docx(value, is_draft=False)
    doc = Document(BytesIO(data))
    assert doc.paragraphs[0].text == value.title
    assert doc.paragraphs[0].runs[0].font.size == Pt(18)
    assert doc.paragraphs[1].runs[0].font.size == Pt(16)
    assert next(p for p in doc.paragraphs if p.text.startswith('报道介绍')).runs[0].font.size == Pt(12)
    assert str(doc.paragraphs[0].runs[0].font.color.rgb) == 'FF0000'
    assert doc.paragraphs[1].text == ('2026年10月19日到10月25日' if kind == 'weekly' else '2026年10月1日到10月31日')
    assert doc.paragraphs[1]._p.pPr.find(qn('w:autoSpaceDN')).get(qn('w:val')) == '0'
    assert abs(doc.sections[0].left_margin - Mm(31.75)) < 1000
    assert abs(doc.sections[0].page_width - Mm(210)) < 1000
    assert '一、油气管网' in [p.text for p in doc.paragraphs]
    assert sum(p.text == '数据源：' for p in doc.paragraphs) == 2
    assert not any('参考资料' in p.text or '{{' in p.text for p in doc.paragraphs)
    with ZipFile(BytesIO(data)) as archive:
        xml = archive.read('word/document.xml').decode()
        rels = archive.read('word/_rels/document.xml.rels').decode()
        styles = archive.read('word/styles.xml').decode()
    assert all(color in styles for color in ['F8FBF6', 'FEFCF2', 'F6F8FC'])
    assert 'w:hyperlink' in xml and 'https://example.org/news' in rels
    assert '检测技术公开报道' in xml and '检测方法研究' in xml
    assert build_pdf(value, is_draft=False)[2].startswith(b'%PDF-')


def test_digest_exports_share_fixed_line_heights_and_pdf_headings_are_bold(monkeypatch) -> None:
    from app.research.services import digest_export

    captured = []
    original = digest_export.SimpleDocTemplate.build

    def inspect(self, flowables, *args, **kwargs):
        captured.extend(flowables)
        return original(self, flowables, *args, **kwargs)

    monkeypatch.setattr(digest_export.SimpleDocTemplate, 'build', inspect)
    value = report()
    word = Document(BytesIO(build_docx(value, is_draft=False)[2]))
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    pdf_paragraphs = [p for p in captured if hasattr(p, 'style')]
    assert len(word.paragraphs) == len(pdf_paragraphs)
    for paragraph, pdf_paragraph in zip(word.paragraphs, pdf_paragraphs, strict=True):
        assert paragraph.paragraph_format.line_spacing.pt == pdf_paragraph.style.leading
        assert paragraph._p.pPr.find(qn('w:spacing')).get(qn('w:lineRule')) == 'exact'
    # FangSong often ships without a bold face. The PDF must explicitly paint
    # bold headings and reset the text state so normal body text stays normal.
    streams = b''.join(page.get_contents().get_data() for page in pdf.pages)
    assert streams.count(b'2 Tr') == 7  # masthead, period, category, two events, two source labels
    assert streams.count(b'0 Tr') >= 7
    assert sum(page.extract_text().count('检测技术验证进展') for page in pdf.pages) == 1


def _pagination_report(filler=0, kind='weekly'):
    value = report(kind)
    value.content = (
        '**跨页校验**\n\n### 1. 需与正文保持相邻的事件标题\n\n'
        + '正文用于覆盖不同页尾位置。' * filler
        + '\n\n发布时间：2026-10-21\n\n行业洞察：'
        + '结论需要运行数据验证，不能由报道直接推断。' * 6
        + '\n\n数据源：\n\n'
        + '\n\n'.join(
            f'[{i}] [第{i}条来源标题：' + '管道运行与试验记录' * 6 + f'](https://example.org/source/{i})'
            for i in range(1, 5)
        )
    )
    return value


def test_word_keeps_headings_and_complete_event_metadata_together() -> None:
    doc = Document(BytesIO(build_docx(_pagination_report(30), is_draft=False)[2]))
    for _index, paragraph in enumerate(doc.paragraphs):
        if paragraph.text.startswith(('一、', '1.', '发布时间：', '行业洞察：', '数据源：', '[')):
            assert paragraph.paragraph_format.keep_together, paragraph.text
        if paragraph.text.startswith(('发布时间：', '行业洞察：', '数据源：', '[1]', '[2]', '[3]')):
            assert paragraph.paragraph_format.keep_with_next, paragraph.text
    assert doc.paragraphs[-1].paragraph_format.keep_with_next is False


@pytest.mark.parametrize('filler', [15, 20, 25, 30, 35, 40, 45, 50])
@pytest.mark.parametrize('kind', ['weekly', 'monthly'])
def test_pdf_keeps_insight_date_and_all_sources_on_one_page_at_page_boundaries(filler, kind) -> None:
    import re

    pdf = PdfReader(BytesIO(build_pdf(_pagination_report(filler, kind), is_draft=False)[2]))
    pages = [re.sub(r'\s+', '', page.extract_text()) for page in pdf.pages]
    targets = ['发布时间：2026-10-21', '行业洞察：', '数据源：'] + [f'[{i}]第{i}条来源标题：' for i in range(1, 5)]
    locations = [next(i for i, text in enumerate(pages) if target in text) for target in targets]
    assert len(set(locations)) == 1, (filler, locations)
    links = [a.get_object()['/A']['/URI'] for page in pdf.pages for a in page.get('/Annots', [])]
    assert set(links) == {f'https://example.org/source/{i}' for i in range(1, 5)}


def test_oversized_digest_metadata_can_flow_without_losing_sources_or_failing_export() -> None:
    value = _pagination_report(20)
    value.content += '\n\n' + '\n\n'.join(
        f'[{i}] [第{i}条较长的来源：' + '完整保留来源及其原始链接。' * 10 + f'](https://example.org/source/{i})'
        for i in range(5, 25)
    )
    pdf = PdfReader(BytesIO(build_pdf(value, is_draft=False)[2]))
    assert len(pdf.pages) > 1
    links = [a.get_object()['/A']['/URI'] for page in pdf.pages for a in page.get('/Annots', [])]
    assert set(links) == {f'https://example.org/source/{i}' for i in range(1, 25)}
