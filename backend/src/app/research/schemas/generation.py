from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApplyGenerationResultModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    expected_version: int = Field(ge=1)


class ReportRewriteModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid')
    expected_version: int = Field(ge=1)
    expected_revision: str = Field(min_length=1, max_length=100)
    section_id: str = Field(min_length=1, max_length=100)
    start: int = Field(ge=0, le=1_000_000)
    end: int = Field(ge=1, le=1_000_000)
    text: str = Field(min_length=1, max_length=6000)
    mode: Literal['polish', 'shorten', 'expand'] = 'polish'
