from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, model_validator
from pydantic.alias_generators import to_camel

from app.business_ids import parse_business_id, wire_id
from app.research.digest_policy import DIGEST_SELECTION_LIMIT

BusinessId = Annotated[int, BeforeValidator(parse_business_id), PlainSerializer(wire_id, return_type=str)]


class PipelineListModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    rows: list[dict] = Field(description='列表数据')
    total: int = Field(description='总数')
    counts: dict[str, int] = Field(default_factory=dict, description='按内容类型统计的数量')
    next_cursor: str | None = Field(default=None, description='下一页游标')


class PipelineTemplateSaveModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    purpose: Literal['article', 'research', 'digest']
    prompt: str = Field(min_length=1, max_length=100000)
    description: str = Field(default='', max_length=1000)
    model_id: BusinessId | None = None
    image_model_id: BusinessId | None = None
    sections: list[dict] = Field(default_factory=list, max_length=100)
    image_config: dict = Field(default_factory=dict)
    is_enabled: bool = True


class PipelineReportExportCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    export_format: Literal['docx', 'pdf'] = Field(alias='format', description='导出格式')
    allow_draft: bool = Field(default=False, description='旧客户端请求兼容字段；导出不再经过人工复核')


class PipelineWorkspaceItemMutationModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    item_id: BusinessId = Field(description='正整数业务ID；HTTP使用十进制字符串')
    item_type: Literal['file', 'material', 'article', 'paper', 'report'] = Field(
        default='material', description='业务条目类型'
    )
    action: Literal['favorite', 'basket'] = Field(description='工作区动作')
    title: str = Field(default='', description='仅请求提示；服务端重新读取真实标题')
    snapshot: dict = Field(default_factory=dict, description='条目快照')


class PipelineResearchJobCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=128, description='客户端幂等请求标识')
    report_id: BusinessId | None = Field(default=None, description='重生成的本人报告ID')
    type: Literal['article', 'research', 'daily', 'weekly', 'monthly'] | None = None
    title: str = Field(min_length=1, max_length=500, description='任务名称')
    report_type: str = Field(default='research-demand', description='报告类型')
    template_id: BusinessId | None = Field(default=None, description='已选模板ID')
    template_version: str | None = Field(default=None, description='模板版本显示值快照')
    direction: str = Field(default='', description='研究方向')
    project: str = Field(default='', description='项目名称')
    scenario: str = Field(default='', description='业务场景')
    period: list[str] = Field(default_factory=list, description='起止时间')
    keywords: list[str] = Field(default_factory=list, description='关键词')
    requirements: str = Field(default='', description='生成要求')
    diagram: bool = Field(default=False, description='是否生成结构化图形')
    citation_check: bool = Field(default=True, description='是否检查引用')
    selected_item_ids: list[BusinessId] = Field(default_factory=list, description='选中资料ID')
    materials: list[dict] = Field(
        default_factory=list, description='显式选材：type 为 article/paper/file，id 为来源主键'
    )
    outline: list[dict] = Field(default_factory=list, description='报告大纲')
    options: dict = Field(default_factory=dict, description='扩展配置')

    @model_validator(mode='after')
    def validate_digest_selection_limit(self) -> 'PipelineResearchJobCreateModel':
        if self.type is not None:
            self.report_type = self.type
        if self.materials and self.selected_item_ids:
            raise ValueError('请使用一种选材方式，不要同时提交 materials 和 selectedItemIds')
        selections = self.materials or self.selected_item_ids
        if len(selections) > DIGEST_SELECTION_LIMIT:
            raise ValueError(f'每次生成最多选择 {DIGEST_SELECTION_LIMIT} 条资料，请减少勾选后重试；不会截断已选资料')
        for selection in self.materials:
            if selection.get('type') not in {'article', 'paper', 'file'} or selection.get('id') is None:
                raise ValueError('选材须包含有效 type（article/paper/file）和 id')
            selection['id'] = wire_id(selection['id'])
        return self


class PipelineDigestCandidatesModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    period: list[date] = Field(min_length=1, max_length=2)
    sources: list[Literal['新闻网站', '微信公众号']] = Field(min_length=1, max_length=2)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    directions: list[str] = Field(default_factory=list, max_length=10)
    page_num: int = Field(default=1, ge=1)
    page_size: Literal[10, 20, 50] = 10

    @model_validator(mode='after')
    def validate_period(self) -> 'PipelineDigestCandidatesModel':
        if self.period[0] > self.period[-1]:
            raise ValueError('报告周期的开始日期不能晚于结束日期')
        if any(len(term) > 200 for term in [*self.keywords, *self.directions]):  # noqa: PLR2004
            raise ValueError('筛选关键词过长')
        return self


class PipelineDigestScheduleCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=128, description='客户端幂等请求标识')
    name: str = Field(min_length=1, max_length=255, description='计划名称')
    report_type: Literal['daily', 'weekly', 'monthly'] = Field(description='日报、周报或月报')
    template_id: BusinessId = Field(description='已启用模板ID')
    template_version: str | None = Field(default=None, max_length=32, description='模板版本快照')
    schedule_time: str = Field(
        default='08:00',
        pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$',
        description='本地执行时间，格式为HH:MM',
    )
    schedule_weekday: int = Field(default=0, ge=0, le=6, strict=True, description='每周执行日，0为周一，6为周日')
    schedule_month_day: int = Field(
        default=1, ge=1, le=31, strict=True, description='每月执行日期，不足该日期的月份在月末执行'
    )
    holiday_policy: Literal['run', 'skip'] = Field(default='run', description='配置日期命中节假日时继续执行或跳过')
    holiday_dates: list[str] = Field(default_factory=list, description='按YYYY-MM-DD填写需要处理的节假日日期')
    direction: str = Field(default='', max_length=2000, description='技术方向')
    keywords: list[str] = Field(default_factory=list, description='关键词')
    requirements: str = Field(default='', max_length=5000, description='生成要求')
    outline: list[dict] = Field(default_factory=list, description='报告大纲')
    options: dict = Field(default_factory=dict, description='周期筛选和生成配置')
    enabled: bool = Field(default=True, description='是否启用')
    timezone: str = Field(default='Asia/Shanghai', min_length=1, max_length=64, description='IANA执行时区')
    selection_config: dict = Field(default_factory=dict, description='周期筛选和去重参数，不保存本次勾选快照')
    generation_config: dict = Field(default_factory=dict, description='生成参数，模板中配置文本及图片模型')


class PipelineDigestScheduleToggleModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    enabled: bool = Field(description='是否启用自动计划')


class PipelineReportUpdateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str | None = Field(default=None, max_length=500, description='报告标题')
    content: str | None = Field(default=None, description='Markdown正文')
    sections: list[dict] | None = Field(default=None, description='结构化章节')
    citations: list[dict] | None = Field(default=None, description='引用证据')
    quality_issues: list[dict] | None = Field(default=None, description='质量问题')
    status: str | None = Field(default=None, description='报告状态')
    expected_version: int | None = Field(default=None, ge=1, description='客户端最近一次读取的报告版本')
    expected_revision: str | None = Field(default=None, description='客户端最近一次读取的报告修订标记')
    save_version: bool = Field(default=False, description='是否保存为新版本')
    version_source: str = Field(default='manual', description='版本来源')


class PipelineDiagramUpdateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    schema_version: int = Field(default=1, ge=1, le=1, description='图形数据结构版本')
    diagram: dict = Field(description='结构化技术路线图数据')
