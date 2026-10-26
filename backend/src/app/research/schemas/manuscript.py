from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.intelligence.schemas.pipeline import BusinessId


class ManuscriptGenerateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    topic: str = Field(description='论文题目')
    description: str | None = Field(default='', description='研究背景与生成要求')
    keywords: list[str] = Field(default_factory=list, description='关键词')
    provided_references: list[str] = Field(default_factory=list, description='人工提供参考文献')
    manual_sections: dict[str, str] | None = Field(default=None, description='人工补充章节材料')
    custom_outline: dict[str, Any] | None = Field(default=None, description='自定义章节框架')
    custom_options: dict[str, Any] | None = Field(default=None, description='自定义生成选项')
    template_type: str = Field(default='review', description='模板类型')
    language: str = Field(default='zh', description='生成语言')
    visual_mode: str = Field(default='direct', description='图表生成模式')
    template_id: BusinessId | None = Field(default=None, description='用户选择的后台模板 ID')
    selected_item_ids: list[BusinessId] = Field(default_factory=list, max_length=50, description='真实资料 ID')


class ManuscriptTitleSuggestModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    description: str = Field(default='', description='研究描述')
    keywords: list[str] = Field(default_factory=list, description='关键词')


class ManuscriptJobModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str = Field(description='生成任务ID')
    topic: str = Field(description='论文题目')
    status: str = Field(description='任务状态')
    current_stage: str = Field(description='当前阶段')
    progress_pct: int = Field(description='进度百分比')
    template_type: str = Field(description='模板类型')
    keywords: list[str] = Field(description='关键词')
    created_at: str = Field(description='创建时间')
    updated_at: str = Field(description='更新时间')
    stages: list[dict] = Field(description='生成阶段')
    outline: list[dict] = Field(description='论文大纲')
    content: str = Field(description='Markdown 草稿')


class ManuscriptListModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    rows: list[dict] = Field(description='任务列表')
    total: int = Field(description='总数')


class ManuscriptExportModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    file_name: str = Field(description='导出文件名')
    content: str = Field(description='Markdown 内容')


class ManuscriptTitleSuggestResultModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    titles: list[str] = Field(description='候选标题')
