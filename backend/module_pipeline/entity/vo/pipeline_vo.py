from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PipelineMetricModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    label: str = Field(description='指标名称')
    value: int | float | str = Field(description='指标值')
    unit: str = Field(default='', description='单位')
    trend: str = Field(default='stable', description='趋势')


class PipelineStatusModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    name: str = Field(description='名称')
    status: str = Field(description='状态')
    value: int | float = Field(description='数值')


class PipelineDashboardModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    metrics: list[PipelineMetricModel] = Field(description='概览指标')
    collect_status: list[PipelineStatusModel] = Field(description='采集状态')
    hot_topics: list[dict] = Field(description='热点主题')
    pending_reviews: list[dict] = Field(description='待审核内容')


class IntelligenceItemModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: str = Field(description='条目ID')
    category: str = Field(description='类别')
    title: str = Field(description='标题')
    source: str = Field(description='来源')
    source_type: str = Field(description='来源类型')
    publish_time: str = Field(description='发布时间')
    relevance: int = Field(description='管网相关性评分')
    status: str = Field(description='处理状态')
    tags: list[str] = Field(description='标签')
    summary: str = Field(description='摘要')


class IntelligenceDetailModel(IntelligenceItemModel):
    content: str = Field(description='正文')
    related_topics: list[str] = Field(description='关联主题')
    entities: list[dict] = Field(description='抽取实体')
    timeline: list[dict] = Field(description='处理时间线')


class PipelineListModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    rows: list[dict] = Field(description='列表数据')
    total: int = Field(description='总数')


class PipelineSourceModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: str = Field(description='数据源ID')
    name: str = Field(description='数据源名称')
    type: str = Field(description='数据源类型')
    frequency: str = Field(description='采集频率')
    status: str = Field(description='状态')
    last_run_time: str = Field(description='最后运行时间')
    success_rate: int = Field(description='成功率')


class PipelineTaskModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: str = Field(description='任务ID')
    name: str = Field(description='任务名称')
    source: str = Field(description='来源')
    status: str = Field(description='状态')
    progress: int = Field(description='进度')
    latest_message: str = Field(description='最新消息')
    next_run_time: str = Field(description='下次运行时间')


class PipelineReportModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: str = Field(description='报告ID')
    title: str = Field(description='标题')
    type: str = Field(description='报告类型')
    status: str = Field(description='状态')
    owner: str = Field(description='负责人')
    updated_at: str = Field(description='更新时间')
    coverage: int = Field(description='覆盖资讯数')


class PipelineReportExportModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    file_name: str = Field(description='导出文件名')
    content: str = Field(description='Markdown报告内容')


class PipelineKnowledgeAskModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    question: str = Field(description='知识库问题')
    document_ids: list[str] = Field(default_factory=list, description='指定资料ID')
    document_types: list[str] = Field(default_factory=list, description='指定资料分类')


class PipelineKnowledgeAnswerModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    answer: str = Field(description='问答结果')
    references: list[dict] = Field(description='引用资料')


class PipelineWorkspaceItemMutationModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    item_id: str = Field(description='业务条目ID')
    item_type: Literal['material', 'article', 'paper', 'report'] = Field(
        default='material', description='业务条目类型'
    )
    action: Literal['favorite', 'basket'] = Field(description='工作区动作')
    title: str = Field(description='标题快照')
    snapshot: dict = Field(default_factory=dict, description='条目快照')


class PipelineResearchJobCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str = Field(min_length=1, max_length=500, description='任务名称')
    report_type: str = Field(default='research-demand', description='报告类型')
    template_id: str | None = Field(default=None, description='内置模板编码快照')
    template_version: str | None = Field(default=None, description='模板版本显示值快照')
    direction: str = Field(default='', description='研究方向')
    project: str = Field(default='', description='项目名称')
    scenario: str = Field(default='', description='业务场景')
    period: list[str] = Field(default_factory=list, description='起止时间')
    keywords: list[str] = Field(default_factory=list, description='关键词')
    requirements: str = Field(default='', description='生成要求')
    diagram: bool = Field(default=False, description='是否生成结构化图形')
    citation_check: bool = Field(default=True, description='是否检查引用')
    selected_item_ids: list[str] = Field(default_factory=list, description='选中资料ID')
    outline: list[dict] = Field(default_factory=list, description='报告大纲')
    options: dict = Field(default_factory=dict, description='扩展配置')


class PipelineReportUpdateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str | None = Field(default=None, max_length=500, description='报告标题')
    content: str | None = Field(default=None, description='Markdown正文')
    sections: list[dict] | None = Field(default=None, description='结构化章节')
    citations: list[dict] | None = Field(default=None, description='引用证据')
    quality_issues: list[dict] | None = Field(default=None, description='质量问题')
    status: str | None = Field(default=None, description='报告状态')
    save_version: bool = Field(default=False, description='是否保存为新版本')
    version_source: str = Field(default='manual', description='版本来源')


class PipelineDiagramUpdateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    schema_version: int = Field(default=1, ge=1, le=1, description='图形数据结构版本')
    diagram: dict = Field(description='结构化技术路线图数据')
