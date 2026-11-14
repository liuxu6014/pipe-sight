"""简报样例格式与真实选材来源的契约。"""

import json
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
    assert text.splitlines()[0].strip() == '管网科技情报月报'
    assert '2026年10月1日到10月31日' in text
    assert '数据源：' in text


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
