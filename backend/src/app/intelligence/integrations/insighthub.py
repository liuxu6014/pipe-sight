"""PipeSight 与 InsightHub PostgreSQL Worker 的交接适配器。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

try:
    import asyncpg
except ImportError:  # Optional until InsightHub handoff is enabled.
    asyncpg = None  # type: ignore[assignment]

from config.env import InsightHubConfig, InsightHubSettings

if TYPE_CHECKING:
    from app.intelligence.models.collection import PipelineSource
    from app.intelligence.models.content import PipelineArticle


class InsightHubAdapter:
    """Write collected news into the deployed InsightHub PostgreSQL schema."""

    def __init__(self, settings: InsightHubSettings = InsightHubConfig) -> None:
        self.settings = settings
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', settings.insighthub_db_schema):
            raise ValueError('InsightHub schema name is invalid')

    async def _next_id(self, conn: Any, table_name: str, column_name: str) -> int:
        """Allocate an ID for the deployed schema, which currently has no sequence."""
        # ponytail: MAX+1 is acceptable for the low-rate handoff path; replace with a
        # shared sequence when InsightHub exposes one to all writers.
        await conn.execute("SELECT pg_advisory_xact_lock(318742, 1)")
        return int(
            await conn.fetchval(
                f'SELECT COALESCE(MAX({column_name}), 0) + 1 FROM {self._schema}.{table_name}'
            )
        )

    async def _connect(self) -> Any:
        if not self.settings.insighthub_enabled or not self.settings.insighthub_db_password:
            raise RuntimeError('InsightHub integration is not configured')
        if asyncpg is None:
            raise RuntimeError('InsightHub integration requires the asyncpg package')
        ssl = 'require' if self.settings.insighthub_db_sslmode == 'require' else False
        return await asyncpg.connect(
            host=self.settings.insighthub_db_host,
            port=self.settings.insighthub_db_port,
            database=self.settings.insighthub_db_name,
            user=self.settings.insighthub_db_user,
            password=self.settings.insighthub_db_password,
            ssl=ssl,
            timeout=self.settings.insighthub_db_timeout_seconds,
        )

    @property
    def _schema(self) -> str:
        return self.settings.insighthub_db_schema

    @staticmethod
    def _content_type(source_type: str) -> str:
        normalized = (source_type or '').lower()
        if 'rss' in normalized:
            return 'RSS'
        if 'json' in normalized or 'api' in normalized:
            return 'JSON'
        if 'html' in normalized or 'web' in normalized:
            return 'HTML'
        return 'Other'

    @staticmethod
    def _db_datetime(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=None) if value and value.tzinfo else value

    async def check_connection(self) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "select current_database() as database, current_user as user_name, current_setting('TimeZone') as timezone"
            )
            return dict(row)
        finally:
            await conn.close()

    async def _ensure_source(self, conn: Any, source: PipelineSource) -> int:
        source_code = source.processor_source_code or source.source_code
        existing = await conn.fetchrow(
            f'SELECT web_source_id FROM {self._schema}.data_sources WHERE web_name = $1',
            source_code,
        )
        source_url = source.endpoint or f'pipeSight://{source.source_code}'
        source_meta = json.dumps(
            {'pipesight_source_id': source.source_id, 'pipesight_source_code': source.source_code},
            ensure_ascii=False,
        )
        if existing:
            await conn.execute(
                f"""
                UPDATE {self._schema}.data_sources
                SET url = $2,
                    web_name_cn = $3,
                    content_type = $4,
                    other = $5,
                    last_crawled_timestamp = now()
                WHERE web_source_id = $1
                """,
                existing['web_source_id'],
                source_url,
                source.name,
                self._content_type(source.source_type),
                source_meta,
            )
            return existing['web_source_id']

        web_source_id = await self._next_id(conn, 'data_sources', 'web_source_id')
        return await conn.fetchval(
            f"""
            INSERT INTO {self._schema}.data_sources
                (web_source_id, web_name, web_name_cn, url, content_type, other, create_time, data_source_classify)
            VALUES ($1, $2, $3, $4, $5, $6, now(), '1')
            RETURNING web_source_id
            """,
            web_source_id,
            source_code,
            source.name,
            source_url,
            self._content_type(source.source_type),
            source_meta,
        )

    async def submit_articles(
        self,
        source: PipelineSource,
        articles: list[PipelineArticle],
    ) -> list[dict[str, Any]]:
        """Idempotently stage articles in InsightHub; the external worker processes them afterward."""

        if not articles:
            return []
        conn = await self._connect()
        try:
            async with conn.transaction():
                web_source_id = await self._ensure_source(conn, source)
                results: list[dict[str, Any]] = []
                for article in articles:
                    existing = await conn.fetchrow(
                        f"""
                        SELECT news_id, create_time, prompt_trace_id
                        FROM {self._schema}.articles
                        WHERE uuid = $1
                        ORDER BY create_time DESC
                        LIMIT 1
                        """,
                        article.article_id,
                    )
                    create_time = self._db_datetime(article.discovered_time) or datetime.now()
                    publish_time = self._db_datetime(article.published_time) or create_time
                    tags = json.dumps(article.tags or [], ensure_ascii=False)
                    metadata = json.dumps(article.metadata_json or {}, ensure_ascii=False)
                    values = (
                        article.title,
                        article.body,
                        article.summary,
                        web_source_id,
                        create_time,
                        publish_time,
                        source.name,
                        article.canonical_url,
                        article.canonical_url,
                        article.article_id,
                        tags,
                        metadata,
                        'W' if article.article_type == 'wechat' else 'N',
                    )
                    if existing and existing['prompt_trace_id'] is None:
                        await conn.execute(
                            f"""
                            UPDATE {self._schema}.articles
                            SET original_title = $3,
                                original_text = $4,
                                summary = $5,
                                web_source_id = $6,
                                publish_time = $7,
                                source = $8,
                                external_link = $9,
                                url = $10,
                                tags = $11,
                                news_all_info = $12,
                                type = $13,
                                filter_result = NULL,
                                processing_attempts = 0,
                                processing_status = 'pending',
                                processing_started_at = NULL,
                                processing_completed_at = NULL,
                                processing_error = NULL,
                                del_flag = '0',
                                prompt_trace_id = NULL
                            WHERE news_id = $1 AND create_time = $2 AND prompt_trace_id IS NULL
                            """,
                            existing['news_id'],
                            existing['create_time'],
                            article.title,
                            article.body,
                            article.summary,
                            web_source_id,
                            publish_time,
                            source.name,
                            article.canonical_url,
                            article.canonical_url,
                            tags,
                            metadata,
                            values[12],
                        )
                        external_id = existing['news_id']
                        external_time = existing['create_time']
                    else:
                        if existing and existing['create_time']:
                            previous_time = self._db_datetime(existing['create_time'])
                            create_time = max(
                                create_time,
                                datetime.now(),
                                previous_time + timedelta(microseconds=1),
                            )
                            values = (*values[:4], create_time, *values[5:])
                        news_id = await self._next_id(conn, 'articles', 'news_id')
                        external_id, external_time = await conn.fetchrow(
                            f"""
                            INSERT INTO {self._schema}.articles
                                (news_id, original_title, original_text, summary, web_source_id, create_time, publish_time,
                                 source, external_link, url, uuid, tags, news_all_info, type, platform)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 0)
                            RETURNING news_id, create_time
                            """,
                            news_id,
                            *values[:12],
                            values[12],
                        )
                    results.append(
                        {
                            'article_id': article.article_id,
                            'handoff_record_id': str(external_id),
                            'handoff_create_time': external_time,
                            'handoff_status': (
                                'processing'
                                if existing is None or existing['prompt_trace_id']
                                else 'dispatched'
                            ),
                        }
                    )
                return results
        finally:
            await conn.close()

    async def fetch_processing_results(self, article_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Read the latest InsightHub result for each PipeSight article ID."""
        if not article_ids:
            return {}
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                    SELECT DISTINCT ON (uuid)
                    uuid, news_id, create_time, prompt_trace_id, ai_title, summary,
                    domain_id, domain, classify, score, warning_grade, warning_cause,
                    focus_risk, suggestion, event_keywords, filter_result, del_flag,
                    processing_status, processing_attempts, processing_error
                FROM {self._schema}.articles
                WHERE uuid = ANY($1::varchar[])
                ORDER BY uuid, create_time DESC
                """,
                article_ids,
            )
            results: dict[str, dict[str, Any]] = {}
            for row in rows:
                data = dict(row)
                processing_status = data.get('processing_status')
                data['status'] = (
                    'rejected'
                    if data.get('del_flag') == '2' or processing_status == 'rejected'
                    else 'failed'
                    if processing_status in {'failed', 'dead_letter'}
                    else 'completed'
                    if processing_status == 'completed' or data.get('prompt_trace_id')
                    else 'processing'
                )
                data['result'] = {
                    key: data.get(key)
                    for key in (
                        'ai_title', 'summary', 'domain_id', 'domain', 'classify', 'score',
                        'warning_grade', 'warning_cause', 'focus_risk', 'suggestion',
                        'event_keywords', 'filter_result', 'processing_status',
                        'processing_attempts', 'processing_error',
                    )
                    if data.get(key) is not None
                }
                results[str(data['uuid'])] = data
            return results
        finally:
            await conn.close()
