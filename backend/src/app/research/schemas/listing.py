from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page: int = Field(default=1, ge=1, alias='pageNum')
    page_size: int = Field(default=20, ge=1, le=100, alias='pageSize')
    keyword: str = Field(default='', max_length=200)
    status: str = Field(default='', max_length=32)
    kind: Literal['', 'research', 'digest', 'brief', 'daily', 'weekly', 'monthly'] = ''
    sort: Literal['', 'updated-desc', 'updated-asc', 'generated-desc', 'generated-asc', 'title', 'title-desc'] = ''
    start: str = Field(default='', pattern=r'^(?:\d{4}-\d{2}-\d{2})?$')
    end: str = Field(default='', pattern=r'^(?:\d{4}-\d{2}-\d{2})?$')


class MaterialListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page: int = Field(default=1, ge=1, alias='pageNum')
    page_size: int = Field(default=20, ge=1, le=100, alias='pageSize')
    keyword: str = Field(default='', max_length=200)
    status: str = Field(default='', max_length=32)
    classification: str = Field(default='', max_length=100)


class JobListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page: int = Field(default=1, ge=1, alias='pageNum')
    page_size: int = Field(default=20, ge=1, le=100, alias='pageSize')
    keyword: str = Field(default='', max_length=200)
    status: Literal['', 'all', 'active', 'queued', 'running', 'completed', 'failed', 'cancelled'] = ''
