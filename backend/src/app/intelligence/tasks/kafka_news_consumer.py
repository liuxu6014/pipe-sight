"""持续运行的 Kafka 新闻消费端：把外部爬虫推送到 topic `news` 的文章写入内容库。

外部爬虫（172.16.4.181）把公众号/网站原文推送到 Kafka topic `news`，消息体是
InsightHub 的 ``NewsBase`` JSON（id/title/content/content_md/ctime/url/author/
site_name/abstract/domain/…）。本模块是一个独立、常驻的消费进程：

- 订阅 `news`，独立消费组（缺省 `pipesight_news_consumer`），不与其他消费端争抢分区；
- 每条消息解析后写入当前（旧版）内容契约 ``public.news_articles``，与
  ``scripts/import_wechat_feeds.py``、``scripts/import_curated_content.py`` 一致；
- 幂等：按 ``url_hash`` / ``canonical_url`` / ``article_id`` 去重；
- ``review_status='approved'``（用户要求「不需审核」直接入库）；
- 手动按消息提交 offset，解析失败跳过、写入失败不提交（重试），Kafka 断连自动重连。

运行（与其它脚本一致，需指定目标环境）：

    APP_ENV=prod pipesight-kafka-consumer                     # 常驻消费（缺省从最新开始）
    pipesight-kafka-consumer --from-earliest --limit 50       # 回溯历史并只处理前 50 条
    pipesight-kafka-consumer --dry-run --limit 10             # 只打印映射结果、不写库不提交

目标数据库守卫：**仅允许生产 ``172.16.4.183/pipesight``**，其它任何目标（含本地）直接拒绝，
避免误写。当生产完成新内容契约迁移后，本模块的 INSERT 语句需同步更新。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import signal
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import psycopg2
from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata
from psycopg2.extras import Json

from app.infrastructure.services.logging_support import logger

BEIJING = ZoneInfo('Asia/Shanghai')
ADAPTER_KEY = 'kafka_news_import'
REASON = '外部爬虫经 Kafka topic「news」推送的原文；未调用大模型、未构造评分或交接结果'
ADVISORY_LOCK = 2026110102

DEFAULT_BOOTSTRAP_SERVERS = '172.16.4.169:19092,172.16.4.169:29092,172.16.4.169:39092'
DEFAULT_TOPIC = 'news'
DEFAULT_GROUP_ID = 'pipesight_news_consumer'


def clean_text(value: str | None) -> str:
    """去掉 HTML 标签并折叠空白，与既有采集器一致。"""
    if not value:
        return ''
    value = re.sub(r'<script\b[^>]*>.*?</script>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<style\b[^>]*>.*?</style>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def normalize_url(value: str | None) -> str | None:
    """返回无片段、无凭据的稳定文章 URL；非法或空返回 None。"""
    value = (value or '').strip()
    if not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        return None
    host = parts.hostname.lower()
    return urlunsplit((parts.scheme, host, parts.path or '/', parts.query, ''))


def beijing_naive(dt: datetime | None) -> datetime | None:
    """把（可能带时区的）时间点归一为无时区的北京墙钟时间。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING)
    return dt.astimezone(BEIJING).replace(tzinfo=None)


def now_beijing() -> datetime:
    return datetime.now(BEIJING).replace(tzinfo=None)


def parse_ctime(value: object) -> datetime | None:
    """解析 NewsBase.ctime（unix 秒或日期字符串）为无时区北京时间。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return beijing_naive(datetime.fromtimestamp(float(value), tz=timezone.utc))
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            try:
                return beijing_naive(datetime.fromtimestamp(int(text), tz=timezone.utc))
            except (OverflowError, OSError, ValueError):
                return None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                return beijing_naive(datetime.strptime(text, fmt))
            except ValueError:
                continue
        try:
            return beijing_naive(datetime.fromisoformat(text.replace('Z', '+00:00')))
        except ValueError:
            return None
    return None


def article_type_of(url: str | None) -> str:
    """按链接域名推断内容类型：公众号 mp.weixin.qq.com 为 wechat，其余为 news。"""
    try:
        host = (urlsplit(url or '').hostname or '').lower()
    except ValueError:
        host = ''
    return 'wechat' if host.endswith('mp.weixin.qq.com') else 'news'


def target() -> dict:
    from config.env import DataBaseConfig as config  # noqa: PLC0415

    if config.db_type != 'postgresql':
        raise ValueError('拒绝非 PostgreSQL 目标')
    if (config.db_host, config.db_database) != ('172.16.4.183', 'pipesight'):
        raise ValueError(f'仅允许 172.16.4.183/pipesight，拒绝目标: {config.db_host}/{config.db_database}')
    return {
        'host': config.db_host,
        'port': config.db_port,
        'dbname': config.db_database,
        'user': config.db_username,
        'password': config.db_password,
        'connect_timeout': 8,
    }


def map_message(data: dict, now: datetime) -> tuple[dict, str, str, str] | None:
    """把 NewsBase 形态的 Kafka 消息映射为旧版 news_articles 字段。

    返回 (article, source_name, article_type, source_code)；消息缺少 URL 或标题时返回 None。
    """
    url = normalize_url(data.get('url'))
    title = (data.get('title') or '').strip()
    if not url or not title:
        return None

    article_type = article_type_of(url)
    source_name = (data.get('site_name') or '').strip() or '未知来源'

    content_md = (data.get('content_md') or '').strip()
    content = data.get('content') or ''
    translated = (data.get('translated_text') or '').strip()
    body = content_md or clean_text(content) or translated
    summary = (data.get('abstract') or '').strip()[:300] or body[:300]

    score = data.get('score')
    relevance_score = float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 0.0
    language = 'zh-CN' if re.search(r'[一-鿿]', body) else 'en'

    article_id = 'kafka-' + hashlib.sha256(url.encode()).hexdigest()[:24]
    source_code = 'kafka-news-' + hashlib.sha256(source_name.encode()).hexdigest()[:20]

    metadata = {
        'ingestion_mode': 'kafka',
        'llm_used': False,
        'embedding_created': False,
        'producer': 'insight_hub',
        'crawler_id': data.get('id'),
        'site_name': source_name,
        'domain': data.get('domain'),
        'domain_id': data.get('domain_id'),
        'category_id': data.get('category_id'),
        'sector': data.get('sector'),
        'features': data.get('features'),
        'cover_image_url': data.get('cover_image_url') or data.get('image_url') or '',
        'ai_title': data.get('ai_title'),
        'translated_title': data.get('translated_title'),
        'translated_text': data.get('translated_text'),
        'translate_mod': data.get('translate_mod'),
        'platform': data.get('platform'),
        'data_source_classify': data.get('data_source_classify'),
        'content_extraction': data.get('content_extraction'),
        'event_keywords': data.get('event_keywords'),
        'final_news_id': data.get('final_news_id'),
        'country': data.get('country'),
        'warning_level': data.get('warning_level'),
        'risk_reason': data.get('risk_reason'),
        'score': relevance_score,
        'received_at': now.isoformat(),
    }

    article = {
        'article_id': article_id,
        'article_type': article_type,
        'title': title[:1000],
        'canonical_url': url,
        'url_hash': hashlib.sha256(url.encode()).hexdigest(),
        'source_name': source_name[:255],
        'author_text': (data.get('author') or source_name)[:255],
        'published_time': parse_ctime(data.get('ctime')),
        'discovered_time': now,
        'language': language,
        'summary': summary,
        'body': body,
        'relevance_score': relevance_score,
        'review_status': 'approved',
        'reviewed_at': now,
        'review_reason': REASON,
        'published_at': now,
        'permission_scope': 'public',
        'tags': Json([]),
        'metadata_json': Json(metadata),
        'handoff_status': 'pending',
        'handoff_result_json': Json({}),
        'version_no': 1,
        'create_time': now,
        'update_time': now,
    }
    return article, source_name, article_type, source_code


INSERT_SOURCE = """
    INSERT INTO public.data_sources (
        source_id, source_code, name, source_type, endpoint, adapter_key,
        schedule_cron, status, enabled, config_json, handoff_mode
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_ARTICLE = """
    INSERT INTO public.news_articles (
        article_id, article_type, title, canonical_url, url_hash,
        source_id, source_name, author_text, published_time, discovered_time,
        language, summary, body, relevance_score, review_status, reviewed_at,
        review_reason, published_at, permission_scope, tags, metadata_json,
        handoff_status, handoff_result_json, version_no, create_time, update_time
    ) VALUES (
        %(article_id)s, %(article_type)s, %(title)s, %(canonical_url)s, %(url_hash)s,
        %(source_id)s, %(source_name)s, %(author_text)s, %(published_time)s, %(discovered_time)s,
        %(language)s, %(summary)s, %(body)s, %(relevance_score)s, %(review_status)s, %(reviewed_at)s,
        %(review_reason)s, %(published_at)s, %(permission_scope)s, %(tags)s, %(metadata_json)s,
        %(handoff_status)s, %(handoff_result_json)s, %(version_no)s, %(create_time)s, %(update_time)s
    )
"""


def ensure_source(cursor, source_code: str, source_name: str, article_type: str, topic: str, now: datetime) -> str:
    """返回该 site_name 对应的 source_id，首次出现时创建 data_sources 行。"""
    cursor.execute('SELECT source_id FROM public.data_sources WHERE source_code=%s', (source_code,))
    row = cursor.fetchone()
    if row:
        return row[0]
    source_id = 'kafka-' + hashlib.sha256(source_name.encode()).hexdigest()[:24]
    cursor.execute(
        INSERT_SOURCE,
        (
            source_id,
            source_code,
            source_name[:255],
            article_type,
            f'kafka://{topic}',
            ADAPTER_KEY,
            None,
            'active',
            True,
            Json({'topic': topic, 'site_name': source_name, 'ingestion': 'kafka'}),
            'local',
        ),
    )
    return source_id


def store_message(db_cfg: dict, data: dict, topic: str) -> str:
    """写入单条消息（同步，运行在 asyncio.to_thread 中），返回 'inserted' 或 'skipped'。"""
    now = now_beijing()
    mapped = map_message(data, now)
    if mapped is None:
        return 'skipped'
    article, source_name, article_type, source_code = mapped

    with psycopg2.connect(**db_cfg) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADVISORY_LOCK,))
            source_id = ensure_source(cursor, source_code, source_name, article_type, topic, now)
            article['source_id'] = source_id
            for column, value in (('article_id', article['article_id']), ('url_hash', article['url_hash'])):
                cursor.execute(
                    f'SELECT article_id FROM public.news_articles WHERE {column}=%s', (value,)
                )
                if cursor.fetchone():
                    return 'skipped'
            cursor.execute(
                'SELECT article_id FROM public.news_articles WHERE canonical_url=%s', (article['canonical_url'],)
            )
            if cursor.fetchone():
                return 'skipped'
            cursor.execute(INSERT_ARTICLE, article)
    return 'inserted'


async def _handle_message(db_cfg: dict, msg, topic: str, dry_run: bool) -> str:
    """处理单条 Kafka 消息，返回 'inserted'/'skipped'/'error'。"""
    raw = msg.value
    if raw is None:
        return 'skipped'
    try:
        data = json.loads(raw.decode('utf-8')) if isinstance(raw, (bytes, bytearray)) else raw
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        logger.warning('忽略无法解析的 Kafka 消息（partition=%s offset=%s）：%s', msg.partition, msg.offset, exc)
        return 'skipped'
    if not isinstance(data, dict):
        logger.warning('忽略非 JSON 对象的 Kafka 消息：%s', type(data).__name__)
        return 'skipped'
    if dry_run:
        _preview(data)
        return 'skipped'
    try:
        return await asyncio.to_thread(store_message, db_cfg, data, topic)
    except Exception as exc:
        logger.error('写入失败（不提交 offset，稍后重试）：%s', exc)
        await asyncio.sleep(1)
        return 'error'


def _preview(data: dict) -> None:
    """dry-run：打印映射结果供人工核对，不写库。"""
    mapped = map_message(data, now_beijing())
    if mapped is None:
        print(json.dumps({'skipped': True, 'reason': 'missing url/title'}, ensure_ascii=False))
        return
    article, source_name, article_type, source_code = mapped
    print(
        json.dumps(
            {
                'article_type': article_type,
                'source': source_name,
                'source_code': source_code,
                'title': article['title'],
                'url': article['canonical_url'],
                'published_time': article['published_time'].isoformat() if article['published_time'] else None,
                'body_length': len(article['body']),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


async def _consume_loop(consumer: AIOKafkaConsumer, db_cfg: dict | None, topic: str, args, stop_event: asyncio.Event) -> None:
    stats = {'received': 0, 'inserted': 0, 'skipped': 0, 'errors': 0}
    last_log = time.monotonic()
    try:
        while not stop_event.is_set():
            try:
                batch = await asyncio.wait_for(consumer.getmany(timeout_ms=1000), timeout=10)
            except asyncio.TimeoutError:
                continue
            for _tp, records in batch.items():
                for msg in records:
                    if stop_event.is_set():
                        break
                    stats['received'] += 1
                    outcome = await _handle_message(db_cfg, msg, topic, args.dry_run)
                    stats['inserted' if outcome == 'inserted' else 'skipped' if outcome == 'skipped' else 'errors'] += 1
                    if not args.dry_run and outcome != 'error':
                        try:
                            partition = TopicPartition(msg.topic, msg.partition)
                            await consumer.commit({partition: OffsetAndMetadata(msg.offset + 1, '')})
                        except Exception as exc:
                            logger.warning('提交 offset 失败：%s', exc)
                    if args.limit and stats['received'] >= args.limit:
                        stop_event.set()
                        break
                if stop_event.is_set():
                    break
            if time.monotonic() - last_log >= 30:
                logger.info('Kafka 消费统计：%s', stats)
                last_log = time.monotonic()
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def _run(consumer: AIOKafkaConsumer, db_cfg: dict | None, topic: str, args, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await consumer.start()
            logger.info('Kafka 消费端已连接（topic=%s group=%s），开始常驻消费。', topic, args.group_id)
            await _consume_loop(consumer, db_cfg, topic, args, stop_event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('Kafka 消费循环异常，5 秒后重连：%s', exc)
            await asyncio.sleep(5)


async def _main_async(consumer: AIOKafkaConsumer, db_cfg: dict | None, args) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except (NotImplementedError, RuntimeError):
        # Windows 或非主线程事件循环不支持 signal handler；取消任务仍可退出。
        pass
    await _run(consumer, db_cfg, args.topic, args, stop_event)


def main() -> None:
    parser = argparse.ArgumentParser(description='持续运行的 Kafka 新闻消费端')
    parser.add_argument('--bootstrap-servers', default=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', DEFAULT_BOOTSTRAP_SERVERS))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', DEFAULT_TOPIC))
    parser.add_argument('--group-id', default=os.environ.get('KAFKA_GROUP_ID', DEFAULT_GROUP_ID))
    parser.add_argument('--from-earliest', action='store_true', help='从最早 offset 回溯历史消息（缺省 latest）')
    parser.add_argument('--dry-run', action='store_true', help='只解析并打印映射结果，不写库、不提交 offset')
    parser.add_argument('--limit', type=int, default=0, help='最多处理 N 条后退出（0 表示常驻）')
    args = parser.parse_args()

    if args.limit < 0:
        raise SystemExit('--limit 不能为负数')

    db_cfg = None
    if not args.dry_run:
        db_cfg = target()

    offset_reset = 'earliest' if args.from_earliest else 'latest'
    consumer = AIOKafkaConsumer(
        args.topic,
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        auto_offset_reset=offset_reset,
        enable_auto_commit=False,
    )

    try:
        asyncio.run(_main_async(consumer, db_cfg, args))
    except KeyboardInterrupt:
        logger.info('Kafka 消费端收到中断信号。')


if __name__ == '__main__':
    main()
