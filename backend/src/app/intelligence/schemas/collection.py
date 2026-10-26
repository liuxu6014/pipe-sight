"""采集域独立 DTO；共享 pipeline.py 由主代理集成。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic.alias_generators import to_camel


class SourceSave(BaseModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)
    name: str = Field(min_length=1, max_length=255)
    type: Literal['website', 'wechat', 'paper']
    url: str | None = None
    adapter: str = Field(min_length=1, max_length=128)
    cron: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default='Asia/Shanghai', min_length=1, max_length=64)
    config: dict = Field(default_factory=dict)
    model_id: int | None = None
    is_enabled: StrictBool = True


class SourceEnabled(BaseModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)
    is_enabled: StrictBool


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)
    request_id: str = Field(min_length=1, max_length=128)


class IsolationConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)
    worker_isolated: StrictBool
