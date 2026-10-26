"""模型管理 DTO：统一实体字段与旧界面 keys 显式适配。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator
from pydantic.alias_generators import to_camel

from app.business_time import format_business_time


class AiModelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)
    id: int | None = None
    name: str | None = None
    provider: Literal['openai', 'openai-compatible', 'compatible', 'deepseek'] | None = Field(
        default=None,
        description='仅支持 OpenAI 兼容协议；其他厂商的兼容端点请明确选择 compatible，暂不支持 Anthropic/Qwen 原生协议',
    )
    code: str | None = None
    base_url: str | None = None
    credential_ref: str | None = None
    capabilities: list[Literal['text_generate', 'image_generate', 'image_input', 'reasoning']] | None = None
    parameters: dict[str, Any] | None = None
    is_enabled: bool | None = None
    # 仅 DTO 兼容，绝不映射 ORM 同名列。
    model_id: int | None = None
    model_name: str | None = None
    model_code: str | None = None
    api_key: str | None = Field(default=None, exclude=True)
    status: Literal['0', '1'] | None = None
    model_type: str | None = None
    support_images: Literal['Y', 'N'] | None = None
    support_reasoning: Literal['Y', 'N'] | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0, le=2)
    model_sort: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer('created_at', 'updated_at')
    def audit_time_text(self, value: datetime | None) -> str:
        return format_business_time(value)

    @model_validator(mode='after')
    def adapt(self):
        self.id = self.id if self.id is not None else self.model_id
        self.name = self.name if self.name is not None else self.model_name
        self.code = self.code if self.code is not None else self.model_code
        if self.is_enabled is None and self.status is not None:
            self.is_enabled = self.status == '0'
        if self.capabilities is None and self.model_type:
            if self.model_type in {'image', 'image_generate'}:
                self.capabilities = ['image_generate']
            elif self.model_type in {'text', 'chat', 'llm', 'text_generate'}:
                self.capabilities = ['text_generate']
        # supportImages 旧字段仅表示图片输入，不推断图片生成。
        if self.support_images == 'Y' and self.capabilities is not None and 'image_input' not in self.capabilities:
            self.capabilities = [*self.capabilities, 'image_input']
        return self

    def get_model_code(self):
        return self.code

    def get_base_url(self):
        return self.base_url


class AiModelPageQueryModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    model_id: int | None = None
    model_name: str | None = None
    provider: str | None = None
    status: Literal['0', '1'] | None = None
    capability: str | None = None
    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class DeleteAiModelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    model_ids: str


class AiModelTestResultModel(BaseModel):
    model_id: int
    model_code: str
    provider: str
    success: bool
    latency_ms: int
    capability: str = 'text_generate'
    response_preview: str | None = None
    message: str
    tested_at: datetime
