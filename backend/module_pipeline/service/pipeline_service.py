from __future__ import annotations

from datetime import datetime


class PipelineService:
    """Lightweight domain service for the pipeline intelligence MVP."""

    _intelligence_items = [
        {
            'id': 'news-001',
            'category': 'news',
            'title': '长输管道智能巡检与多源感知融合成为行业关注重点',
            'source': '能源科技观察',
            'source_type': 'news',
            'publish_time': '2026-07-11 09:30:00',
            'relevance': 92,
            'status': 'processed',
            'tags': ['智能巡检', '多源感知', '长输管道'],
            'summary': '多家能源企业将无人机、光纤传感和边缘识别纳入管道完整性管理试点。',
            'content': '行业报道显示，管道企业正在将多源感知、边缘计算和智能识别能力组合用于高后果区巡检，重点解决巡检频次高、人工筛选慢和异常复核难的问题。',
            'related_topics': ['管道完整性管理', '边缘智能', '缺陷识别'],
            'entities': [{'type': 'technology', 'name': '光纤传感'}, {'type': 'scenario', 'name': '高后果区'}],
            'timeline': [{'time': '09:35', 'label': '采集'}, {'time': '09:38', 'label': '清洗'}, {'time': '09:41', 'label': '标签生成'}],
        },
        {
            'id': 'wechat-001',
            'category': 'wechat',
            'title': '油气储运装备数字化运维专题研讨发布',
            'source': '管道技术前沿',
            'source_type': 'wechat',
            'publish_time': '2026-07-10 18:20:00',
            'relevance': 86,
            'status': 'reviewing',
            'tags': ['数字化运维', '装备管理', '科研需求'],
            'summary': '文章围绕设备状态评估、智能诊断和维修策略优化提出多项科研方向。',
            'content': '公众号文章总结了油气储运装备数字化运维的关键痛点，并建议建立跨站场数据治理机制，把现场问题转化为可验证的科研课题。',
            'related_topics': ['装备运维', '数据治理', '智能诊断'],
            'entities': [{'type': 'organization', 'name': '储运装备'}, {'type': 'technology', 'name': '智能诊断'}],
            'timeline': [{'time': '18:25', 'label': '采集'}, {'time': '18:30', 'label': '去重'}, {'time': '18:36', 'label': '待审核'}],
        },
        {
            'id': 'paper-001',
            'category': 'paper',
            'title': '基于磁各向异性传感的管道缺陷识别与本体应力监测综述',
            'source': 'Journal of Pipeline Systems',
            'source_type': 'paper',
            'publish_time': '2026-07-09 14:00:00',
            'relevance': 95,
            'status': 'processed',
            'tags': ['磁各向异性', '缺陷识别', '应力监测'],
            'summary': '论文综述磁各向异性传感在管道本体应力监测和缺陷识别中的应用。',
            'content': '该论文对磁各向异性传感机理、现场布设方式和数据解释模型进行了系统综述，适合作为“管道本体应力监测技术研究”的技术路线参考。',
            'related_topics': ['磁应力监测', '本体缺陷', '检测算法'],
            'entities': [{'type': 'technology', 'name': '磁各向异性'}, {'type': 'task', 'name': '应力监测'}],
            'timeline': [{'time': '14:05', 'label': '论文入库'}, {'time': '14:12', 'label': '结构化解析'}, {'time': '14:18', 'label': '方向归类'}],
        },
        {
            'id': 'paper-002',
            'category': 'paper',
            'title': '长输油气管道多元检测数据融合与缺陷优先级评估',
            'source': 'Energy Engineering Letters',
            'source_type': 'paper',
            'publish_time': '2026-07-08 11:10:00',
            'relevance': 89,
            'status': 'processed',
            'tags': ['多元检测', '数据融合', '缺陷评估'],
            'summary': '论文提出多模态检测数据融合方法，用于提升长输管道缺陷评估稳定性。',
            'content': '研究将漏磁、超声、几何变形和历史维修记录统一建模，输出缺陷优先级，为维修决策提供依据。',
            'related_topics': ['多元检测', '缺陷评估', '维修决策'],
            'entities': [{'type': 'technology', 'name': '漏磁检测'}, {'type': 'technology', 'name': '超声检测'}],
            'timeline': [{'time': '11:16', 'label': '论文入库'}, {'time': '11:24', 'label': '实体抽取'}, {'time': '11:31', 'label': '摘要生成'}],
        },
    ]

    _sources = [
        {'id': 'src-news', 'name': '能源科技观察', 'type': 'news', 'frequency': '每6小时', 'status': 'enabled', 'last_run_time': '2026-07-12 21:00:00', 'success_rate': 98},
        {'id': 'src-wechat', 'name': '管道技术前沿', 'type': 'wechat', 'frequency': '每日', 'status': 'enabled', 'last_run_time': '2026-07-12 19:00:00', 'success_rate': 94},
        {'id': 'src-paper', 'name': 'Crossref / Semantic Scholar', 'type': 'paper', 'frequency': '每日', 'status': 'enabled', 'last_run_time': '2026-07-12 18:30:00', 'success_rate': 91},
    ]

    _tasks = [
        {'id': 'task-news', 'name': '新闻资讯采集', 'source': '能源科技观察', 'status': 'running', 'progress': 68, 'latest_message': '已解析 34 条候选资讯', 'next_run_time': '2026-07-13 01:00:00'},
        {'id': 'task-wechat', 'name': '公众号文章采集', 'source': '管道技术前沿', 'status': 'success', 'progress': 100, 'latest_message': '本轮新增 12 篇文章', 'next_run_time': '2026-07-13 08:00:00'},
        {'id': 'task-paper', 'name': '论文跟踪采集', 'source': 'Crossref / Semantic Scholar', 'status': 'warning', 'progress': 82, 'latest_message': '2 篇论文需要人工确认方向', 'next_run_time': '2026-07-13 06:30:00'},
    ]

    _reports = [
        {'id': 'report-daily', 'title': '国家管网科技情报日报', 'type': 'daily', 'status': 'reviewing', 'owner': '情报分析组', 'updated_at': '2026-07-12 20:40:00', 'coverage': 42},
        {'id': 'report-weekly', 'title': '管道完整性技术周报', 'type': 'weekly', 'status': 'draft', 'owner': '科研规划组', 'updated_at': '2026-07-12 17:20:00', 'coverage': 126},
        {'id': 'report-monthly', 'title': '管网科技创新月报', 'type': 'monthly', 'status': 'draft', 'owner': '情报分析组', 'updated_at': '2026-07-31 18:00:00', 'coverage': 238},
        {'id': 'report-route', 'title': '磁应力监测技术路线建议', 'type': 'technology-route', 'status': 'planned', 'owner': '专项课题组', 'updated_at': '2026-07-11 16:00:00', 'coverage': 18},
    ]

    _knowledge_documents = [
        {'id': 'doc-design', 'name': '设计方案.docx', 'type': '平台方案', 'scenario': '总体架构、采集处理、知识库与报告生成', 'status': 'indexed', 'keywords': ['平台', '采集', '知识库', '报告']},
        {'id': 'doc-demand', 'name': '平台功能需求分析与进度规划.pdf', 'type': '需求规划', 'scenario': '新闻、公众号、论文展示与统一检索', 'status': 'indexed', 'keywords': ['需求', '检索', '采集', '进度']},
        {'id': 'doc-stress', 'name': '基于磁各向异性原理的管道本体应力监测技术研究_1.docx', 'type': '研究资料', 'scenario': '应力监测、磁各向异性、传感器与现场试验', 'status': 'indexed', 'keywords': ['磁各向异性', '应力监测', '传感器']},
        {'id': 'doc-defect', 'name': '津华管道多元检测数据缺陷智能化分析算法及应用.docx', 'type': '研究资料', 'scenario': '多元检测、缺陷识别、算法验证', 'status': 'planned', 'keywords': ['多元检测', '缺陷识别', '算法']},
    ]

    @classmethod
    def get_dashboard_summary(cls) -> dict:
        processed_count = len([item for item in cls._intelligence_items if item['status'] == 'processed'])
        return {
            'metrics': [
                {'label': '有效资讯', 'value': 42, 'unit': '条', 'trend': 'up'},
                {'label': '待审核', 'value': 6, 'unit': '条', 'trend': 'stable'},
                {'label': 'L1分类准确率', 'value': 87, 'unit': '%', 'trend': 'up'},
                {'label': '已处理条目', 'value': processed_count, 'unit': '条', 'trend': 'stable'},
            ],
            'collect_status': [
                {'name': '新闻采集', 'status': 'running', 'value': 68},
                {'name': '公众号采集', 'status': 'success', 'value': 100},
                {'name': '论文采集', 'status': 'warning', 'value': 82},
            ],
            'hot_topics': [
                {'name': '管道完整性管理', 'heat': 96, 'count': 18},
                {'name': '磁应力监测', 'heat': 91, 'count': 12},
                {'name': '多元检测数据融合', 'heat': 88, 'count': 10},
            ],
            'pending_reviews': cls._reports,
        }

    @classmethod
    def list_intelligence(
        cls,
        category: str | None = None,
        keyword: str | None = None,
        source_type: str | None = None,
        page_num: int = 1,
        page_size: int = 10,
    ) -> dict:
        rows = cls._intelligence_items
        if category:
            rows = [item for item in rows if item['category'] == category]
        if source_type:
            rows = [item for item in rows if item['source_type'] == source_type]
        if keyword:
            normalized_keyword = keyword.lower()
            rows = [
                item
                for item in rows
                if normalized_keyword in item['title'].lower()
                or normalized_keyword in item['summary'].lower()
                or normalized_keyword in item['content'].lower()
                or any(normalized_keyword in tag.lower() for tag in item['tags'])
            ]
        total = len(rows)
        start = max(page_num - 1, 0) * page_size
        end = start + page_size
        return {'rows': rows[start:end], 'total': total}

    @classmethod
    def get_intelligence_detail(cls, item_id: str) -> dict:
        for item in cls._intelligence_items:
            if item['id'] == item_id:
                return item
        raise ValueError(f'Intelligence item not found: {item_id}')

    @classmethod
    def list_sources(cls) -> dict:
        return {'rows': cls._sources, 'total': len(cls._sources)}

    @classmethod
    def list_tasks(cls) -> dict:
        return {'rows': cls._tasks, 'total': len(cls._tasks)}

    @classmethod
    def run_collect_task(cls, task_id: str) -> dict:
        for task in cls._tasks:
            if task['id'] == task_id:
                task['status'] = 'success'
                task['progress'] = 100
                task['latest_message'] = f'手动运行完成：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 已完成采集、清洗和标签生成'
                return task
        raise ValueError(f'Collect task not found: {task_id}')

    @classmethod
    def list_reports(cls) -> dict:
        return {'rows': cls._reports, 'total': len(cls._reports)}

    @classmethod
    def export_report_markdown(cls, report_id: str) -> str:
        report = next((item for item in cls._reports if item['id'] == report_id), None)
        if not report:
            raise ValueError(f'Report not found: {report_id}')
        topics = cls.get_dashboard_summary()['hot_topics']
        items = cls._intelligence_items[:3]
        topic_lines = '\n'.join(f'- {topic["name"]}：热度 {topic["heat"]}，关联 {topic["count"]} 条' for topic in topics)
        item_lines = '\n'.join(f'- **{item["title"]}**（{item["source"]}）：{item["summary"]}' for item in items)
        return (
            f'# {report["title"]}\n\n'
            f'- 报告类型：{report["type"]}\n'
            f'- 负责人：{report["owner"]}\n'
            f'- 覆盖资讯：{report["coverage"]} 条\n'
            f'- 更新时间：{report["updated_at"]}\n\n'
            '## 重点主题\n\n'
            f'{topic_lines}\n\n'
            '## 代表性情报\n\n'
            f'{item_lines}\n\n'
            '## 初步研判\n\n'
            '磁各向异性、本体应力监测和多元检测数据融合适合作为近期科研路线的重点方向。建议优先沉淀数据标准、现场验证方案和指标体系。\n'
        )

    @classmethod
    def list_knowledge_documents(cls) -> dict:
        return {'rows': cls._knowledge_documents, 'total': len(cls._knowledge_documents)}
