"""常驻 Kafka 内容消费端：统一 envelope → 处理（翻译/分类）→ 入库有效数据。

本进程订阅 `news_pipeline`（`KafkaSettings` 缺省 broker 为 `172.16.4.182:9092`）。
优先解析统一 envelope `KafkaContentMessage`（见 `app.intelligence.schemas.kafka_message`）；
对象不符合 envelope 时，再兼容扁平 JSON
``{title,url,author,ctime,content,content_md,site_name,domain}``
（映射进统一 envelope 再走同一条处理链路，只覆盖新闻和公众号）。该形状与
news-pipelines 的 `NewsArticlesPipeline.map_message` 读取格式一致。news-pipelines
当前代码没有把抓取结果发到这个主题的生产者。本进程使用独立消费组
（缺省 `pipesight_news_consumer`），不与其他消费端争抢分区：

- 解析并校验统一 envelope，非法消息跳过（提交 offset，不阻塞分区）；
- 按 content_type 幂等创建/复用 data_sources 来源（wechat 按 config.bizid）；
- 处理：来源配置了翻译模型且缺中文时翻译；启用了类别时分类；
- 只写「有效数据」——标题/URL/DOI/去重校验失败的一律不入库；
- 手动按消息提交 offset：写入失败不提交（重试），Kafka 断连自动重连。

运行（与其它脚本一致，需指定目标环境）：

    APP_ENV=prod pipesight-kafka-consumer                  # 常驻消费（缺省从最新开始）
    pipesight-kafka-consumer --from-earliest --limit 50    # 回溯历史并只处理前 50 条
    pipesight-kafka-consumer --dry-run --limit 10          # 只打印映射、不写库

目标数据库守卫：仅允许 172.16.4.183/pipesight。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import signal
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.business_ids import wire_id
from app.infrastructure.models.registry import register_sqlalchemy_models
from app.infrastructure.services.logging_support import logger
from app.intelligence.schemas.kafka_message import KafkaContentMessage
from app.intelligence.services.categories import CategoryService
from app.intelligence.services.collection_persistence import CollectionPersistenceService
from app.intelligence.services.collection_translation import (
    CollectionTranslationService,
    TranslationConfigurationError,
    TranslationFailure,
)
from app.intelligence.services.entities import EntityExtractionService
from config.database import AsyncSessionLocal
from config.env import DataBaseConfig, KafkaConfig
from config.get_db import close_async_engine, init_create_table

ADAPTER_KEY = 'kafka_content_import'
CONTENT_TYPE_TO_SOURCE_TYPE = {'news': 'website', 'wechat': 'wechat', 'paper': 'paper'}
TARGET_HOST = '172.16.4.183'
TARGET_DATABASE = 'pipesight'
STATS_LOG_INTERVAL_SECONDS = 30


def _guard_target() -> None:
    """仅允许写生产 183/pipesight，其它目标直接拒绝。"""
    if (DataBaseConfig.db_host, DataBaseConfig.db_database) != (TARGET_HOST, TARGET_DATABASE):
        raise RuntimeError(
            f'仅允许 {TARGET_HOST}/{TARGET_DATABASE}，拒绝目标: {DataBaseConfig.db_host}/{DataBaseConfig.db_database}'
        )


def _unix_seconds_to_iso(value: Any) -> str | None:
    """把爬虫侧 unix 秒时间戳转成带时区的 ISO-8601 字符串；非法返回 None。"""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


_MD_LINK_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)')


def _markdown_to_plain_text(value: str) -> str:
    """把爬虫 markdown 正文转成纯文本，保留空行作为段落分隔。"""
    text = value.replace('\r\n', '\n').replace('\r', '\n')
    text = _MD_LINK_RE.sub(lambda match: match.group(1) or '', text)  # 图片去掉，链接留文字
    text = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', text)  # 标题标记
    text = re.sub(r'(?m)^\s{0,3}>\s?', '', text)  # 引用标记
    text = re.sub(r'(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', text)  # 列表标记
    text = re.sub(r'[ \t]+', ' ', text)  # 折叠行内空白，保留换行
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'(\*\*|__|~~|`)', '', text)  # 行内强调/代码标记
    text = re.sub(r'\n{2,}', '\n\n', text)
    return text.strip()


def _prefer_content(data: dict) -> str | None:
    """优先取保留段落边界的正文：content_md 换行更多时用 markdown 转纯文本。"""
    content = data.get('content')
    content_md = data.get('content_md')
    if isinstance(content_md, str) and content_md.strip():
        if not isinstance(content, str) or content_md.count('\n') > content.count('\n'):
            return _markdown_to_plain_text(content_md)
    return content if isinstance(content, str) and content.strip() else None


def _normalize_crawler_message(data: dict) -> KafkaContentMessage | None:
    """把扁平爬虫 JSON 映射进统一 envelope；缺标题/URL 返回 None。

    news-pipelines 的 `NewsArticlesPipeline.map_message` 读取的是
    ``{title,url,author,ctime(unix秒),content,content_md,site_name,domain}``，
    ``domain == 'mp.weixin.qq.com'`` 视为公众号，其余视为新闻。
    """
    title = data.get('title')
    url = data.get('url')
    if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.strip():
        return None
    domain = data.get('domain') if isinstance(data.get('domain'), str) else ''
    site_name = data.get('site_name') if isinstance(data.get('site_name'), str) else ''
    content = _prefer_content(data)
    return KafkaContentMessage(
        schema_version=1,
        content_type='wechat' if domain == 'mp.weixin.qq.com' else 'news',
        source_name=site_name or domain or '未知来源',
        source_url=f'https://{domain}' if domain else None,
        source_bizid=None,
        item_id=None,
        title=title.strip(),
        url=url.strip(),
        author=data.get('author') if isinstance(data.get('author'), str) else None,
        published_at=_unix_seconds_to_iso(data.get('ctime')),
        content=content if isinstance(content, str) else None,
    )


def _parse_message(raw: Any) -> KafkaContentMessage | None:
    """把 Kafka 消息解析为统一 envelope；无法解析或不符合契约返回 None。"""
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode('utf-8')) if isinstance(raw, (bytes, bytearray)) else raw
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        logger.warning('忽略无法解析的 Kafka 消息：%s', exc)
        return None
    if not isinstance(data, dict):
        logger.warning('忽略非 JSON 对象的 Kafka 消息：%s', type(data).__name__)
        return None
    try:
        return KafkaContentMessage.model_validate(data)
    except ValidationError:
        # 兼容 news-pipelines 爬虫侧历史格式（映射进统一 envelope）。
        message = _normalize_crawler_message(data)
        if message is None:
            logger.warning('忽略不符合统一 envelope 的消息：%s', sorted(data))
        return message


def _to_record(message: KafkaContentMessage) -> dict:
    """把统一 envelope 映射为 news_articles / papers 的候选记录。"""
    if message.content_type == 'paper':
        return {
            'title': message.title,
            'url': message.url,
            'doi': message.doi,
            'title_zh': message.title_zh,
            'authors': message.authors,
            'journal': message.journal,
            'published_date': message.published_date,
            'abstract': message.abstract or message.content,
            'abstract_zh': message.abstract_zh,
        }
    return {
        'title': message.title,
        'url': message.url,
        'author': message.author,
        'published_at': message.published_at,
        'content': message.content,
        'content_zh': message.content_zh,
    }


async def _ensure_source(db, message: KafkaContentMessage, now) -> Any:
    """幂等返回消息对应的 data_sources 行；首次出现时创建。"""
    from app.intelligence.models.collection import PipelineSource  # noqa: PLC0415

    source_type = CONTENT_TYPE_TO_SOURCE_TYPE[message.content_type]
    if message.content_type == 'wechat' and message.source_bizid:
        row = (
            (
                await db.execute(
                    select(PipelineSource).where(
                        PipelineSource.adapter == ADAPTER_KEY,
                        PipelineSource.config['bizid'].astext == message.source_bizid,
                    )
                )
            )
            .scalars()
            .first()
        )
    else:
        row = (
            (
                await db.execute(
                    select(PipelineSource).where(
                        PipelineSource.adapter == ADAPTER_KEY,
                        PipelineSource.name == message.source_name,
                        PipelineSource.type == source_type,
                    )
                )
            )
            .scalars()
            .first()
        )
    if row is not None:
        return row
    config: dict = {}
    if message.source_bizid:
        config = {'bizid': message.source_bizid, 'account': message.source_name}
    source = PipelineSource(
        name=(message.source_name or '未知来源')[:255],
        type=source_type,
        url=message.source_url,
        adapter=ADAPTER_KEY,
        cron=None,
        timezone='Asia/Shanghai',
        next_run_at=None,
        config=config,
        model_id=None,
        is_enabled=False,
        created_at=now,
        updated_at=now,
    )
    db.add(source)
    await db.flush()
    return source


async def _process_and_save(db, message: KafkaContentMessage, now) -> str:
    """处理单条消息并写有效数据，返回 'inserted' 或 'skipped'。"""
    source = await _ensure_source(db, message, now)
    record = _to_record(message)

    # 处理：翻译（来源配置了模型且缺中文时），失败保留爬虫原文/译文。
    snapshot = {
        'type': source.type,
        'model_id': source.model_id,
        'source': {'id': wire_id(source.id), 'name': source.name},
    }
    try:
        snapshot = await CollectionTranslationService.freeze(db, snapshot)
        sessions = async_sessionmaker(bind=db.bind, expire_on_commit=False, autoflush=False)
        (record,) = await CollectionTranslationService.translate(sessions, snapshot, [record])
    except (TranslationConfigurationError, TranslationFailure) as exc:
        logger.warning('翻译跳过（保留原文）：%s', exc)

    # 处理：分类（启用了类别时），失败按未分类入库。
    kind = 'paper' if source.type == 'paper' else 'news'
    if source.type == 'paper':
        classify_content = json.dumps(
            {
                key: record.get(key)
                for key in ('doi', 'authors', 'journal', 'published_date', 'abstract', 'abstract_zh')
            },
            ensure_ascii=False,
        )
    else:
        classify_content = record.get('content_zh') or record.get('content') or ''
    try:
        category_id = await CategoryService.classify(db, title=record['title'], content=classify_content, kind=kind)
    except Exception as exc:
        logger.warning('分类失败，按未分类入库：%s', exc)
        category_id = None

    # 新闻概括核心事件，论文仅用标题与摘要；失败不覆盖已有结果。
    entity_content = (
        record.get('abstract_zh') or record.get('abstract') or ''
        if kind == 'paper'
        else record.get('content_zh') or record.get('content') or ''
    )
    try:
        enrichment = await EntityExtractionService.enrich(
            db,
            title=record['title'],
            content=entity_content,
            model_id=source.model_id,
            kind=kind,
            summary=record.get('summary'),
        )
        if enrichment is not None:
            record.update(enrichment)
    except Exception as exc:
        logger.warning('核心实体处理跳过：%s', exc)

    try:
        saved = await CollectionPersistenceService.save_record(db, source, record, now, category_id=category_id)
        await db.commit()
    except (ValueError, TypeError, KeyError, IntegrityError) as exc:
        await db.rollback()
        logger.warning('拒绝无效内容（不入库）：%s', exc)
        return 'skipped'
    except BaseException:
        await db.rollback()
        raise
    return 'inserted' if saved else 'skipped'


def _preview(message: KafkaContentMessage) -> None:
    print(
        json.dumps(
            {
                'content_type': message.content_type,
                'source_name': message.source_name,
                'title': message.title,
                'url': message.url,
                'doi': message.doi,
                'published_at': message.published_at,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


async def _handle_message(msg, args) -> str:
    message = _parse_message(msg.value)
    if message is None:
        return 'skipped'
    if args.dry_run:
        _preview(message)
        return 'skipped'
    try:
        async with AsyncSessionLocal() as db:
            return await _process_and_save(db, message, datetime.now(timezone.utc))
    except Exception as exc:
        logger.error('处理消息失败（不提交 offset，稍后重试）：%s', exc)
        await asyncio.sleep(1)
        return 'error'


async def _consume_once(stop_event: asyncio.Event, args) -> None:
    consumer = AIOKafkaConsumer(
        KafkaConfig.kafka_topic,
        bootstrap_servers=KafkaConfig.kafka_bootstrap_servers,
        group_id=KafkaConfig.kafka_group_id,
        auto_offset_reset='earliest' if args.from_earliest else 'latest',
        enable_auto_commit=False,
        max_poll_records=100,
    )
    await consumer.start()
    stats = {'received': 0, 'inserted': 0, 'skipped': 0, 'errors': 0}
    last_log = monotonic()
    try:
        while not stop_event.is_set():
            try:
                batch = await asyncio.wait_for(consumer.getmany(timeout_ms=1000), timeout=10)
            except asyncio.TimeoutError:
                continue
            for records in batch.values():
                for msg in records:
                    if stop_event.is_set() or (args.limit and stats['received'] >= args.limit):
                        break
                    stats['received'] += 1
                    outcome = await _handle_message(msg, args)
                    if outcome == 'inserted':
                        stats['inserted'] += 1
                    elif outcome == 'skipped':
                        stats['skipped'] += 1
                    else:
                        stats['errors'] += 1
                    if not args.dry_run and outcome != 'error':
                        try:
                            await consumer.commit(
                                {TopicPartition(msg.topic, msg.partition): OffsetAndMetadata(msg.offset + 1, '')}
                            )
                        except Exception as exc:
                            logger.warning('提交 offset 失败：%s', exc)
                    if args.limit and stats['received'] >= args.limit:
                        stop_event.set()
                        break
                if stop_event.is_set():
                    break
            if monotonic() - last_log >= STATS_LOG_INTERVAL_SECONDS:
                logger.info('Kafka 消费统计：%s', stats)
                last_log = monotonic()
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _run(stop_event: asyncio.Event, args) -> None:
    while not stop_event.is_set():
        try:
            await _consume_once(stop_event, args)
        except Exception as exc:  # noqa: PERF203 —— Kafka 断连自动重连
            logger.error('Kafka 消费异常，5 秒后重连：%s', exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='dev', help='运行环境（由 config.env 读取对应 .env 文件）')
    parser.add_argument('--from-earliest', action='store_true', help='从分区最早开始消费')
    parser.add_argument('--limit', type=int, default=0, help='最多处理条数（0 表示不限）')
    parser.add_argument('--dry-run', action='store_true', help='只打印映射结果、不写库')
    args = parser.parse_args()

    async def runner() -> None:
        if not args.dry_run:
            _guard_target()
            register_sqlalchemy_models()
            await init_create_table()
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows 或非主线程事件循环不支持 Unix signal handler；取消任务仍可退出。
            pass
        try:
            await _run(stop_event, args)
        finally:
            if not args.dry_run:
                await close_async_engine()

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
