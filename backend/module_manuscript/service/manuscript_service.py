from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


class ManuscriptService:
    """Paper generation service migrated from the manuscript generator workflow."""

    _jobs: dict[str, dict[str, Any]] = {}
    _stage_templates = [
        ('researching', '资料整理', '已汇总主题描述、关键词和人工参考文献'),
        ('outlining', '大纲生成', '已生成论文结构和章节要点'),
        ('writing', '正文撰写', '已形成 Markdown 论文草稿'),
        ('exporting', '导出准备', '已准备 Markdown 导出内容'),
    ]
    _default_references = [
        '国家管网集团. 长输油气管道完整性管理技术指南, 2025.',
        'Pipeline Research Consortium. Multi-source inspection data fusion for pipeline integrity, 2024.',
        'Zhang et al. Magnetic anisotropy sensing for pipeline stress monitoring. Journal of Pipeline Systems, 2025.',
    ]

    @classmethod
    def reset(cls) -> None:
        cls._jobs = {}

    @classmethod
    def generate_manuscript(
        cls,
        *,
        topic: str,
        description: str | None = '',
        keywords: list[str] | None = None,
        provided_references: list[str] | None = None,
        manual_sections: dict[str, str] | None = None,
        custom_outline: dict[str, Any] | None = None,
        custom_options: dict[str, Any] | None = None,
        template_type: str = 'review',
        language: str = 'zh',
        visual_mode: str = 'direct',
    ) -> dict[str, Any]:
        topic = (topic or '').strip()
        if not topic:
            raise ValueError('topic is required')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        job_id = f'ms-{datetime.now().strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:8]}'
        normalized_keywords = cls._clean_list(keywords)
        references = cls._clean_list(provided_references) or cls._default_references
        outline = cls._build_outline(template_type, custom_outline)
        content = cls._build_markdown(
            topic=topic,
            description=(description or '').strip(),
            keywords=normalized_keywords,
            references=references,
            outline=outline,
            manual_sections=manual_sections or {},
            template_type=template_type,
            custom_options=custom_options or {},
        )
        job = {
            'job_id': job_id,
            'topic': topic,
            'description': (description or '').strip(),
            'keywords': normalized_keywords,
            'provided_references': references,
            'template_type': template_type or 'review',
            'language': language or 'zh',
            'visual_mode': visual_mode or 'direct',
            'status': 'completed',
            'current_stage': 'exporting',
            'progress_pct': 100,
            'created_at': now,
            'updated_at': now,
            'stages': cls._completed_stages(now),
            'outline': outline,
            'content': content,
            'word_count': len(content),
        }
        cls._jobs[job_id] = job
        return dict(job)

    @classmethod
    def list_manuscripts(
        cls,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page_num: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        rows = list(cls._jobs.values())
        if status:
            rows = [item for item in rows if item['status'] == status]
        if keyword:
            normalized_keyword = keyword.strip().lower()
            rows = [
                item
                for item in rows
                if normalized_keyword in item['topic'].lower()
                or normalized_keyword in item['description'].lower()
                or any(normalized_keyword in value.lower() for value in item['keywords'])
            ]
        rows.sort(key=lambda item: item['created_at'], reverse=True)
        total = len(rows)
        start = max(page_num - 1, 0) * page_size
        end = start + page_size
        return {'rows': [cls._summary(item) for item in rows[start:end]], 'total': total}

    @classmethod
    def get_manuscript(cls, job_id: str) -> dict[str, Any]:
        job = cls._jobs.get(job_id)
        if not job:
            raise ValueError(f'Manuscript job not found: {job_id}')
        return dict(job)

    @classmethod
    def export_manuscript(cls, job_id: str) -> dict[str, str]:
        job = cls.get_manuscript(job_id)
        return {
            'file_name': f'{cls._safe_filename(job["topic"])}.md',
            'content': job['content'],
        }

    @classmethod
    def suggest_titles(cls, description: str, keywords: list[str] | None = None) -> list[str]:
        normalized_keywords = cls._clean_list(keywords)
        focus = normalized_keywords[0] if normalized_keywords else cls._extract_focus(description)
        secondary = normalized_keywords[1] if len(normalized_keywords) > 1 else '管网工程'
        candidates = [
            f'{focus}关键技术及工程应用研究',
            f'面向{secondary}的{focus}方法',
            f'{focus}与{secondary}协同优化综述',
            f'长输管道场景下{focus}评价体系研究',
            f'基于多源数据的{focus}分析方法',
        ]
        return cls._dedupe(candidates)[:5]

    @classmethod
    def _build_outline(cls, template_type: str, custom_outline: dict[str, Any] | None) -> list[dict[str, Any]]:
        sections = (custom_outline or {}).get('sections') if isinstance(custom_outline, dict) else None
        if sections:
            return [
                {
                    'heading': str(item.get('heading') or '').strip(),
                    'level': int(item.get('level') or 1),
                    'description': str(item.get('description') or '').strip(),
                }
                for item in sections
                if str(item.get('heading') or '').strip()
            ]

        templates = {
            'fund': [
                ('立项依据', '说明研究背景、工程需求和科学问题。'),
                ('研究内容与目标', '拆解研究任务、关键指标和预期成果。'),
                ('技术路线', '组织实验、数据、模型和现场验证路线。'),
                ('创新点与应用价值', '凝练理论、方法和工程应用创新。'),
            ],
            'key_research': [
                ('项目背景与需求', '对接国家管网业务场景和攻关目标。'),
                ('关键技术与任务分解', '形成课题、任务和里程碑。'),
                ('试验验证与示范应用', '说明现场验证和工程化路径。'),
                ('组织实施与成果交付', '明确团队、条件和交付物。'),
            ],
            'review': [
                ('引言', '界定研究主题和综述范围。'),
                ('国内外研究进展', '梳理代表性技术路线和文献线索。'),
                ('关键技术与方法', '归纳模型、实验和工程方法。'),
                ('工程应用与讨论', '讨论管网场景的适配性和风险。'),
                ('结论与展望', '总结观点并提出后续研究方向。'),
            ],
        }
        selected = templates.get(template_type or 'review', templates['review'])
        return [
            {'heading': heading, 'level': 1, 'description': description}
            for heading, description in selected
        ]

    @classmethod
    def _build_markdown(
        cls,
        *,
        topic: str,
        description: str,
        keywords: list[str],
        references: list[str],
        outline: list[dict[str, Any]],
        manual_sections: dict[str, str],
        template_type: str,
        custom_options: dict[str, Any],
    ) -> str:
        keyword_text = '；'.join(keywords) if keywords else '管道完整性管理；科研辅助决策'
        reference_summary = '；'.join(references[:3])
        lines = [
            f'# {topic}',
            '',
            '## 摘要',
            cls._abstract(topic, description, keyword_text, template_type),
            '',
            f'**关键词：** {keyword_text}',
            '',
        ]
        for index, section in enumerate(outline, start=1):
            heading = section['heading']
            section_description = section.get('description') or '围绕研究主题展开论证。'
            lines.extend(
                [
                    f'## {index} {heading}',
                    cls._section_paragraph(
                        topic=topic,
                        heading=heading,
                        description=description,
                        section_description=section_description,
                        keywords=keywords,
                        references=references,
                    ),
                    '',
                ]
            )

        if manual_sections:
            lines.extend(['## 附录：人工补充材料'])
            for key, value in manual_sections.items():
                if str(value).strip():
                    lines.extend([f'### {key}', str(value).strip(), ''])

        if custom_options.get('generate_figures'):
            lines.extend(
                [
                    '## 图表建议',
                    '- 建议绘制“数据来源-分析模型-现场验证-成果输出”的技术路线图。',
                    '- 建议补充关键指标对比表，用于支撑工程可行性分析。',
                    '',
                ]
            )

        lines.extend(
            [
                '## 参考文献',
                *[f'{index}. {reference}' for index, reference in enumerate(references, start=1)],
                '',
                '## 生成说明',
                f'本文稿参考论文生成流水线自动形成，已完成资料整理、大纲生成、正文撰写和导出准备。核心参考线索：{reference_summary}。',
            ]
        )
        return '\n'.join(lines).strip() + '\n'

    @classmethod
    def _abstract(cls, topic: str, description: str, keyword_text: str, template_type: str) -> str:
        source = description or f'围绕“{topic}”开展管网工程科研论文写作。'
        template_label = {
            'fund': '基金申请式',
            'key_research': '重点研发式',
            'review': '综述论文式',
        }.get(template_type, '论文式')
        return (
            f'本文面向国家管网科研与工程应用场景，采用{template_label}结构组织“{topic}”相关内容。'
            f'{source} 文稿围绕{keyword_text}展开，兼顾技术路线、现场验证、数据治理和成果转化，'
            '为项目设计管理、课题论证和后续申报材料沉淀提供可编辑草稿。'
        )

    @classmethod
    def _section_paragraph(
        cls,
        *,
        topic: str,
        heading: str,
        description: str,
        section_description: str,
        keywords: list[str],
        references: list[str],
    ) -> str:
        focus = '、'.join(keywords[:3]) if keywords else topic
        evidence = references[0] if references else cls._default_references[0]
        base = description or '该部分结合管网项目设计、技术路线论证和工程实施约束展开。'
        return (
            f'{heading}部分重点说明{section_description}围绕{focus}，需要将业务问题、数据条件、'
            f'模型方法和现场验证闭环组织起来。{base} 参考“{evidence}”等资料，'
            '本节建议进一步补充样本来源、评价指标、风险边界和可复用的设计管理要求。'
        )

    @classmethod
    def _completed_stages(cls, timestamp: str) -> list[dict[str, Any]]:
        return [
            {'key': key, 'label': label, 'status': 'completed', 'message': message, 'finished_at': timestamp}
            for key, label, message in cls._stage_templates
        ]

    @classmethod
    def _summary(cls, job: dict[str, Any]) -> dict[str, Any]:
        keys = [
            'job_id',
            'topic',
            'status',
            'current_stage',
            'progress_pct',
            'template_type',
            'keywords',
            'created_at',
            'updated_at',
            'word_count',
        ]
        return {key: job[key] for key in keys}

    @staticmethod
    def _clean_list(values: list[str] | None) -> list[str]:
        if not values:
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    @staticmethod
    def _extract_focus(description: str) -> str:
        text = (description or '').strip()
        if not text:
            return '管网科研论文'
        for separator in ('，', '。', ',', '.', '；', ';'):
            text = text.split(separator)[0]
        return text[:18] or '管网科研论文'

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        result = []
        for value in values:
            if value not in result:
                result.append(value)
        return result

    @staticmethod
    def _safe_filename(value: str) -> str:
        safe = ''.join(char for char in value.strip() if char not in '\\/:*?"<>|')
        return safe or 'manuscript'
