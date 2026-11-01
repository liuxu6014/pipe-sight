"""Import WeChat 公众号 articles from wechat2rss feeds into the news store.

The external crawler (172.16.4.181) publishes one wechat2rss feed per 公众号.
This script fetches those feeds, parses the RSS items (title, mp.weixin.qq.com
link, pubDate, content:encoded body), and writes them into the current compact
content schema: one `data_sources` row per account (type='wechat') and one
`news_articles` row per item (deduped by url via the md5(url) unique index).

Dry-run by default: it only reports what would change. `--apply` writes rows.
Insertion is idempotent by source `config->>'bizid'` and by article url, so the
script is safe to re-run.

Run from backend with the target env set (same as the other one-off imports):

    .venv/Scripts/python.exe scripts/import_wechat_feeds.py            # dry-run
    .venv/Scripts/python.exe scripts/import_wechat_feeds.py --apply    # write

Targets only the production DB (172.16.4.183/pipesight); any other host/database is refused.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import psycopg2
import requests

BEIJING = ZoneInfo('Asia/Shanghai')
USER_AGENT = 'PipeSight/1.0 (+wechat rss import)'
ADAPTER_KEY = 'wechat_rss_import'
ADVISORY_LOCK = 2026110103

FEEDS = [
    'http://172.16.4.181:8081/feed/3010262663.xml',
    'http://172.16.4.181:8081/feed/3011820463.xml',
    'http://172.16.4.181:8081/feed/3251033283.xml',
    'http://172.16.4.181:8081/feed/2399662023.xml',
    'http://172.16.4.181:8081/feed/2396593600.xml',
    'http://172.16.4.181:8081/feed/3595641400.xml',
    'http://172.16.4.181:8081/feed/3085911678.xml',
    'http://172.16.4.181:8081/feed/3921226256.xml',
    'http://172.16.4.181:8081/feed/3899809654.xml',
    'http://172.16.4.181:8081/feed/3092037718.xml',
    'http://172.16.4.181:8081/feed/3260616101.xml',
    'http://172.16.4.181:8081/feed/3928210810.xml',
    'http://172.16.4.181:8081/feed/3091110512.xml',
    'http://172.16.4.181:8081/feed/3239111210.xml',
    'http://172.16.4.181:8081/feed/3527838665.xml',
    'http://172.16.4.181:8081/feed/3584649438.xml',
    'http://172.16.4.181:8081/feed/2393194506.xml',
]


def clean_text(value: str | None) -> str:
    """Strip tags and collapse whitespace from an HTML body, like the collectors."""
    if not value:
        return ''
    value = re.sub(r'<script\b[^>]*>.*?</script>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<style\b[^>]*>.*?</style>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def normalize_wechat_url(value: str | None) -> str | None:
    """Return a stable article URL without fragment/credentials, or None."""
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
    """Normalize a (possibly tz-aware) instant to Beijing wall time without tz."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING)
    return dt.astimezone(BEIJING).replace(tzinfo=None)


def beijing_aware(dt: datetime | None) -> datetime | None:
    """Return a (possibly naive) instant as tz-aware Beijing time for timestamptz."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING)
    return dt.astimezone(BEIJING)


def now_beijing() -> datetime:
    return datetime.now(BEIJING).replace(tzinfo=None)


def parse_pubdate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return beijing_naive(parsedate_to_datetime(value))
    except (TypeError, ValueError, OverflowError):
        return None


def parse_feed(xml_text: str, feed_url: str, limit: int) -> tuple[str, str, list[dict]]:
    """Parse a wechat2rss RSS document into (account, bizid, items)."""
    root = ET.fromstring(xml_text)
    channel = root.find('channel')
    if channel is None:
        raise ValueError('RSS 缺少 channel 节点')

    account = ''
    title_node = channel.find('title')
    if title_node is not None and title_node.text:
        account = title_node.text.strip()

    match = re.search(r'/feed/(\d+)\.xml$', feed_url)
    bizid = match.group(1) if match else hashlib.sha256(feed_url.encode()).hexdigest()[:16]

    def text_of(node, tag: str) -> str:
        child = node.find(tag)
        return (child.text or '').strip() if child is not None and child.text else ''

    items = []
    for item in channel.findall('item'):
        if limit and len(items) >= limit:
            break
        title = clean_text(text_of(item, 'title'))
        link = text_of(item, 'link') or text_of(item, 'guid')
        if not link:
            link = ''
        body = ''
        for child in item:
            if child.tag == 'encoded' or child.tag.endswith('}encoded') or child.tag.endswith(':encoded'):
                body = child.text or ''
                break
        if not body:
            body = item.findtext('description') or ''
        items.append(
            {
                'title': title,
                'link': link,
                'pub': text_of(item, 'pubDate'),
                'body': body,
                '_feed': feed_url,
            }
        )
    return account, bizid, items


def fetch_feed(feed_url: str, timeout: int) -> str:
    response = requests.get(feed_url, timeout=timeout, headers={'User-Agent': USER_AGENT})
    response.raise_for_status()
    if len(response.content) > 16 * 1024 * 1024:
        raise ValueError('feed 响应超过 16 MiB 限制')
    return response.content.decode('utf-8', errors='replace')


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


def ensure_source(cursor, bizid: str, account: str, feed_url: str) -> tuple[int, bool]:
    """Return (id, created) for a feed, creating the data_sources row once.

    Idempotent by `config->>'bizid'` under this script's adapter.
    """
    cursor.execute(
        "SELECT id FROM public.data_sources WHERE adapter=%s AND config->>'bizid'=%s",
        (ADAPTER_KEY, bizid),
    )
    row = cursor.fetchone()
    if row:
        return row[0], False
    cursor.execute(
        """
        INSERT INTO public.data_sources (
            name, type, url, adapter, cron, timezone, next_run_at, config, model_id, is_enabled
        ) VALUES (%s, 'wechat', %s, %s, NULL, 'Asia/Shanghai', NULL, %s::jsonb, NULL, false)
        RETURNING id
        """,
        (
            (account or f'公众号 {bizid}')[:255],
            feed_url,
            ADAPTER_KEY,
            json.dumps({'feed_url': feed_url, 'bizid': bizid, 'account': account}, ensure_ascii=False),
        ),
    )
    return cursor.fetchone()[0], True


def build_article(
    source_id: int,
    account: str,
    item: dict,
    now: datetime,
) -> dict | None:
    url = normalize_wechat_url(item['link'])
    title = (item['title'] or '').strip()
    if not url or not title:
        return None
    body = clean_text(item['body'])
    published = parse_pubdate(item['pub'])
    return {
        'source_id': source_id,
        'title': title[:1000],
        'url': url,
        'author': (account or None),
        'published_at': beijing_aware(published),
        'content': body,
        'content_zh': None,
        'category_id': None,
        'is_pushed': False,
        'created_at': now,
        'updated_at': now,
    }


INSERT_ARTICLE = """
    INSERT INTO public.news_articles (
        source_id, title, url, author, published_at, content, content_zh,
        category_id, is_pushed, created_at, updated_at
    ) VALUES (
        %(source_id)s, %(title)s, %(url)s, %(author)s, %(published_at)s, %(content)s, %(content_zh)s,
        %(category_id)s, %(is_pushed)s, %(created_at)s, %(updated_at)s
    )
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='写入数据库；缺省为 dry-run')
    parser.add_argument('--limit', type=int, default=0, help='每个 feed 最多导入条数（0 表示全部）')
    parser.add_argument('--feed', action='append', default=None, help='覆盖默认 feed 列表（可多次）')
    parser.add_argument('--timeout', type=int, default=30, help='单个 feed 请求超时秒数')
    args = parser.parse_args()

    feeds = args.feed or FEEDS
    batch = datetime.now(BEIJING).strftime('wechat-rss-%Y%m%d-%H%M%S')
    now = now_beijing()
    config = target()

    receipt = {
        'batch': batch,
        'apply': args.apply,
        'feeds': [],
        'added': 0,
        'skipped': 0,
        'sources': [],
        'sources_created': 0,
    }
    prepared = []  # (account, bizid, item)
    for feed_url in feeds:
        try:
            xml_text = fetch_feed(feed_url, args.timeout)
            account, bizid, items = parse_feed(xml_text, feed_url, args.limit)
        except (requests.RequestException, ValueError, ET.ParseError) as exc:
            receipt['feeds'].append({'feed': feed_url, 'error': str(exc), 'items': 0})
            print(json.dumps({'feed': feed_url, 'error': str(exc)}, ensure_ascii=False), flush=True)
            continue
        receipt['feeds'].append({'feed': feed_url, 'account': account, 'bizid': bizid, 'items': len(items)})
        for item in items:
            if not item['title'] and not item['link']:
                continue
            prepared.append((account, bizid, item))

    if not args.apply:
        for account, bizid, item in prepared:
            receipt['added'] += 1
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return

    with psycopg2.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADVISORY_LOCK,))
            source_ids: dict[str, int] = {}
            for account, bizid, item in prepared:
                feed_url = item['_feed']
                if bizid not in source_ids:
                    source_id, created = ensure_source(cursor, bizid, account, feed_url)
                    source_ids[bizid] = source_id
                    receipt['sources'].append({'bizid': bizid, 'account': account, 'source_id': source_id})
                    if created:
                        receipt['sources_created'] += 1
                source_id = source_ids[bizid]
                article = build_article(source_id, account, item, now)
                if article is None:
                    receipt['skipped'] += 1
                    continue
                cursor.execute('SELECT id FROM public.news_articles WHERE url=%s', (article['url'],))
                if cursor.fetchone():
                    receipt['skipped'] += 1
                    continue
                cursor.execute(INSERT_ARTICLE, article)
                receipt['added'] += 1

    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
