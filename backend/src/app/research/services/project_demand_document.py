"""The official project demand form, backed by the frozen report request."""

import re
from datetime import date

PROJECT_DEMAND_FORMAT = 'project-demand-form-v1'
FORM_TITLE = '科技项目需求表'
PROJECT_DEMAND_TEMPLATE_NAMES = {FORM_TITLE, '科技项目需求填报表'}
MAX_BUDGET_YEAR_COLUMNS = 5

PROJECT_DEMAND_WRITING_RULES = (
    '\n本次使用科技项目需求表。严格按确认大纲的顺序和原章节标题成文，'
    '直接从第一章开始，不另写引言、摘要、编制说明、封面或预算表。'
    '小标题使用普通文字，章节标题单独一行加粗。'
    '经费章节只写测算依据及待确认事项，未知金额留空。'
)

CAPITAL_COSTS = ('设备费', '软件购置费', '其他')
EXPENSE_COSTS = (
    '材料费',
    '燃料动力费',
    '试验检验费',
    '图书资料费',
    '外部加工费',
    '维护及修理费',
    '运输费',
    '租赁费',
    '现场试验费',
    '出版/文献/信息传播/知识产权事务费',
    '咨询费',
    '委托研发支出',
    '技术服务费',
    '培训费',
    '办公费',
    '差旅费',
    '会议费',
    '国际合作与交流费',
    '人员费',
    '劳务费',
    '折旧与摊销费',
    '业务招待费',
    '团体会费',
    '其他费用',
)


def project_demand_form(snapshot: dict, title: str) -> dict | None:
    if snapshot.get('document_format') != PROJECT_DEMAND_FORMAT:
        return None
    request = snapshot.get('request') or {}
    period = request.get('period') or []
    try:
        start, end = (date.fromisoformat(str(value)[:10]) for value in period)
        if end < start:
            raise ValueError
    except ValueError:
        date_label, years = '', ['分年度金额']
    else:
        date_label = f'{start.year}年{start.month}月至{end.year}年{end.month}月'
        years = (
            [f'{year}年' for year in range(start.year, end.year + 1)]
            if end.year - start.year < MAX_BUDGET_YEAR_COLUMNS
            else ['分年度金额']
        )
    fields = [
        ['需求名称', request.get('project') or title],
        ['需求级别', ''],
        ['需求类别', ''],
        ['需求类型', ''],
        ['技术业务域', ''],
        ['技术图谱子技术', ''],
        ['研究起止时间', date_label],
        ['填报单位', ''],
        ['联系人', ''],
        ['联系方式', ''],
        ['填报日期', ''],
    ]
    categories = (
        ('一、资本化预算', CAPITAL_COSTS, 1),
        ('二、费用化预算', EXPENSE_COSTS, len(CAPITAL_COSTS) + 1),
    )
    blanks = [''] * (len(years) + 1)
    rows = []
    for label, costs, start in categories:
        rows.append(['', label, *blanks])
        rows.extend([str(i), cost, *blanks] for i, cost in enumerate(costs, start))
    rows.append(['', '预算合计', *blanks])
    return {
        'organization': '国家石油天然气管网集团有限公司',
        'title': FORM_TITLE,
        'fields': fields,
        'budgetHeaders': ['序号', '预算科目', '小计', *years],
        'budgetRows': rows,
    }


def unnumbered_chapter(title: str) -> str:
    return re.sub(r'^(?:[一二三四五六七八九十]+[、．]|\d+[.、．])\s*', '', title.strip())
