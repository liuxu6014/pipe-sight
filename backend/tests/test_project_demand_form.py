from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from pypdf import PdfReader

from app.research.services.exporters import build_docx, build_pdf
from app.research.services.project_demand_document import PROJECT_DEMAND_FORMAT, project_demand_form
from app.research.services.report_content import ManuscriptValidationError, normalize_task_report


def test_project_form_accepts_empty_provider_subtitle_but_rejects_extra_chapter() -> None:
    snapshot = {
        'document_format': PROJECT_DEMAND_FORMAT,
        'request': {'outline': [{'title': '研究内容'}]},
    }
    sources = [{'id': '18', 'type': 'paper', 'title': '复核论文'}]
    raw = '# 项目标题\n\n## ——现场复核研究\n\n**研究内容**\n\n拟对照复核[paper:18]。'
    result = normalize_task_report(raw, sources, snapshot)
    assert [section['title'] for section in result['sections']] == ['一、研究内容', '参考资料']
    assert '——现场复核研究' not in result['content']
    with pytest.raises(ManuscriptValidationError, match='确认的章节顺序'):
        normalize_task_report(raw.replace('## ——现场复核研究', '## 额外章节\n\n额外正文'), sources, snapshot)


def test_project_form_keeps_confirmed_outline_and_exports_fillable_budget() -> None:
    snapshot = {
        'document_format': PROJECT_DEMAND_FORMAT,
        'request': {
            'project': '管道缺陷复核',
            'period': ['2027-01-01', '2028-12-31'],
            'outline': [{'title': '生产需求及技术问题'}, {'title': '经费需求'}],
        },
    }
    sources = [
        {'id': '18', 'type': 'article', 'title': '未引用的会议资料'},
        {'id': '18', 'type': 'paper', 'title': '复核研究论文', 'source': {'doi': '10.1234/example'}},
    ]
    raw = (
        '**引言**\n\n额外引言。\n\n**一、生产需求及技术问题**\n\n论文介绍了复核方法[paper:18]。\n\n'
        '**经费需求**\n\n需按实际作业量测算。\n\n**参考资料**\n\n模型添加的参考资料。'
    )
    result = normalize_task_report(raw, sources, snapshot)
    assert result['materials'] == sources[1:]
    assert [section['title'] for section in result['sections']] == [
        '一、生产需求及技术问题',
        '二、经费需求',
        '参考资料',
    ]
    assert '论文介绍了复核方法[1]。' in result['content']
    assert '[1] 复核研究论文' in result['content']
    assert '未引用的会议资料' not in result['content'] and '额外引言' not in result['content']
    with pytest.raises(ManuscriptValidationError, match='确认的章节顺序'):
        normalize_task_report(raw.replace('**经费需求**', '**其他内容**'), sources, snapshot)

    form = project_demand_form(snapshot, '验收稿')
    report = SimpleNamespace(title='验收稿', content=result['content'], metadata={'projectDemandForm': form})
    word = Document(BytesIO(build_docx(report, is_draft=False)[2]))
    assert [p.text for p in word.paragraphs[:3]] == [
        '国家石油天然气管网集团有限公司',
        '科技项目需求表',
        '需求名称：管道缺陷复核',
    ]
    table = word.tables[0]
    assert [cell.text for cell in table.rows[0].cells] == ['序号', '预算科目', '小计', '2027年', '2028年']
    assert [cell.text for cell in table.rows[-1].cells][1:] == ['预算合计', '', '', '']
    pdf = PdfReader(BytesIO(build_pdf(report, is_draft=False)[2]))
    assert '科技项目需求表' in pdf.pages[0].extract_text()
    assert '生产需求及技术问题' in pdf.pages[1].extract_text()
    assert '经费预算表（万元）' in pdf.pages[2].extract_text()
    assert '参考资料' in ''.join(page.extract_text() for page in pdf.pages[2:])
