"""统一 Kafka 采集消息契约：news / wechat / paper 三类共用一条 envelope。

本 envelope 是 `pipesight-kafka-consumer` 接受的规范契约，不表示已有生产者在发布。
`content_type` 区分三类，类型专属字段只在该类型下使用；字段是三类的并集，按
`content_type` 取子集。扁平 JSON
``{title,url,author,ctime,content,content_md,site_name,domain}`` 由
`kafka_content_consumer._normalize_crawler_message` 映射进本契约，不在此重复。
该形状是 news-pipelines 消费端读取的消息，不是该仓库当前的发布格式。

业务有效性（URL/DOI 规范化、标题非空、去重）由
`CollectionPersistenceService.save_record` 统一裁决，不在本契约重复实现。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class KafkaContentMessage(BaseModel):
    """统一内容采集消息。"""

    schema_version: int = 1
    content_type: Literal['news', 'wechat', 'paper']

    # 来源身份（映射到 data_sources）
    source_name: str = ''
    source_url: str | None = None
    source_bizid: str | None = None  # 仅 wechat：公众号 bizid

    # 通用内容
    item_id: str | None = None  # 爬虫侧幂等键（可选）
    title: str
    url: str | None = None
    author: str | None = None
    published_at: str | None = None  # ISO-8601，带时区（news/wechat）
    content: str | None = None
    content_zh: str | None = None

    # 论文专属
    doi: str | None = None
    title_zh: str | None = None
    authors: str | None = None
    journal: str | None = None
    published_date: str | None = None  # YYYY[-MM[-DD]]
    abstract: str | None = None
    abstract_zh: str | None = None

    @field_validator('schema_version')
    @classmethod
    def _check_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError('仅支持 schema_version=1')
        return value
