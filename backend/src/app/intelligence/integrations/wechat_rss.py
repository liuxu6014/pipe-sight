"""WeChat 公众号 RSS 采集适配器：从内部 wechat2rss feed 拉取并产出文章批次。

外部爬虫（172.16.4.181）为每个公众号暴露一个 wechat2rss feed
（``http://172.16.4.181:8081/feed/{bizid}.xml``）。本适配器把该 feed 接入受控采集
执行器，产出 news_articles 候选批次，交由 PipelineCollectionService 统一翻译 /
分类 / 有效性裁决后入库。

feed 地址保存在 ``config.feed_url`` 而不是 ``url`` 列：``url`` 仍受全局 HTTPS
白名单约束，而内部 feed 是 HTTP 且带非 443 端口，只能作为配置项由本适配器自行
校验。导入/注册本模块不执行网络请求，也不创建来源。
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from app.intelligence.services.collection import CollectionBatch

WECHAT_FEED_HOSTS = ('172.16.4.181',)
WECHAT_FEED_PORT = 8081
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_TITLE_CHARS = 1000
DEFAULT_LIMIT = 12
MAX_LIMIT = 30
MAX_REQUEST_INTERVAL_SECONDS = 60
USER_AGENT = 'PipeSight/1.0 (+wechat rss collector)'
BEIJING = ZoneInfo('Asia/Shanghai')
# bizid/account 为信息性字段：采集时按 feed 重新推导；保留它们是为了与一次性导入
# 脚本和 Kafka 消费端建档公众号源时写入 config 的约定一致。
COMMON_CONFIG = {'feed_url', 'bizid', 'account', 'limit', 'request_interval'}


_BLOCK_TAG_RE = re.compile(
    r'</?(?:br|p|div|section|article|h[1-6]|li|ul|ol|blockquote|pre|tr|table|figure|figcaption)\b[^>]*>',
    re.I,
)


def _clean_text(value: str | None) -> str:
    """剥去标签与空白，得到单行纯文本（用于标题）。"""
    if not value:
        return ''
    value = re.sub(r'<script\b[^>]*>.*?</script>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<style\b[^>]*>.*?</style>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def _clean_body(value: str | None) -> str:
    """剥去标签与空白，得到保留段落边界（空行）的纯文本正文。"""
    if not value:
        return ''
    value = re.sub(r'<script\b[^>]*>.*?</script>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<style\b[^>]*>.*?</style>', ' ', value, flags=re.I | re.S)
    value = _BLOCK_TAG_RE.sub('\n', value)  # 块级标签先转成段落分隔，避免整篇压成一段
    value = re.sub(r'<[^>]+>', '', value)
    value = html.unescape(value)
    value = re.sub(r'[ \t\r\f\v]+', ' ', value)  # 折叠行内空白，保留换行
    value = re.sub(r' *\n *', '\n', value)
    value = re.sub(r'\n{2,}', '\n\n', value)
    return value.strip()


def _normalize_wechat_url(value: str | None) -> str | None:
    """返回不含片段/凭证的稳定文章链接；非法返回 None。"""
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
    return f'{parts.scheme}://{host}{parts.path or "/"}{"?" + parts.query if parts.query else ""}'


def _parse_pubdate(value: str | None) -> datetime | None:
    """把 RSS pubDate 解析为带时区的北京时间点；无法解析返回 None。"""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING)
    return parsed.astimezone(BEIJING)


def validate_feed_url(url: str | None) -> str:
    """校验并返回规范的 feed 地址；只允许内部 wechat2rss 入口。"""
    from app.intelligence.services.collection import ConfigurationError  # noqa: PLC0415

    if not isinstance(url, str) or not url.strip():
        raise ConfigurationError('公众号 RSS 链接不能为空')
    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise ConfigurationError('公众号 RSS 链接无效') from exc
    valid = (
        parsed.scheme == 'http'
        and parsed.hostname in WECHAT_FEED_HOSTS
        and parsed.port == WECHAT_FEED_PORT
        and not parsed.username
        and not parsed.password
        and re.fullmatch(r'/feed/\d+\.xml', parsed.path or '')
        and not parsed.query
        and not parsed.fragment
    )
    if not valid:
        raise ConfigurationError('公众号 RSS 链接须为 http://172.16.4.181:8081/feed/{bizid}.xml')
    return candidate


def validate_wechat_rss_config(snapshot: dict[str, Any]) -> None:
    """在入队/启用前校验，而不是等到首次网络请求。"""
    from app.intelligence.services.collection import ConfigurationError  # noqa: PLC0415

    config = snapshot['config']
    if set(config) - COMMON_CONFIG:
        raise ConfigurationError('公众号 RSS 适配器含不支持的采集配置，请核对来源设置')
    limit = config.get('limit', DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ConfigurationError(f'采集 limit 必须为 1～{MAX_LIMIT} 的整数')
    interval = config.get('request_interval', 0)
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0 <= interval <= MAX_REQUEST_INTERVAL_SECONDS:
        raise ConfigurationError(f'request_interval 必须为 0～{MAX_REQUEST_INTERVAL_SECONDS} 秒')
    validate_feed_url(config.get('feed_url'))


def _parse_feed(xml_text: str, feed_url: str, limit: int) -> tuple[str, str, list[dict[str, str]]]:
    """解析 wechat2rss RSS 文档为 (account, bizid, items)。"""
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

    def text_of(node: ET.Element, tag: str) -> str:
        child = node.find(tag)
        return (child.text or '').strip() if child is not None and child.text else ''

    items: list[dict[str, str]] = []
    for item in channel.findall('item'):
        if limit and len(items) >= limit:
            break
        title = _clean_text(text_of(item, 'title'))
        link = text_of(item, 'link') or text_of(item, 'guid')
        body = ''
        for child in item:
            if child.tag == 'encoded' or child.tag.endswith('}encoded') or child.tag.endswith(':encoded'):
                body = child.text or ''
                break
        if not body:
            body = item.findtext('description') or ''
        items.append({'title': title, 'link': link, 'pub': text_of(item, 'pubDate'), 'body': body})
    return account, bizid, items


def _to_record(account: str, item: dict[str, str]) -> dict[str, Any] | None:
    """把 RSS item 映射为 news_articles 候选记录；缺链接或标题返回 None。"""
    url = _normalize_wechat_url(item.get('link'))
    title = (item.get('title') or '').strip()
    if not url or not title:
        return None
    return {
        'title': title[:MAX_TITLE_CHARS],
        'url': url,
        'author': account or None,
        'published_at': _parse_pubdate(item.get('pub')),
        'content': _clean_body(item.get('body')),
    }


def _make_client(config: dict[str, Any]) -> httpx.AsyncClient:
    seconds = config.get('request_timeout', 30)
    return httpx.AsyncClient(
        timeout=httpx.Timeout(seconds, connect=min(seconds, 10)),
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        headers={'User-Agent': USER_AGENT},
    )


async def _fetch_feed(client: httpx.AsyncClient, feed_url: str) -> str:
    from app.intelligence.services.collection import ConfigurationError, TransientCollectionError  # noqa: PLC0415

    validate_feed_url(feed_url)
    try:
        async with client.stream('GET', feed_url, headers={'Accept': 'application/xml, text/xml, */*'}) as response:
            if response.status_code in (408, 429) or response.status_code >= 500:  # noqa: PLR2004
                raise TransientCollectionError('公众号 feed 临时不可用')
            if response.status_code != 200:  # noqa: PLR2004
                raise ConfigurationError('公众号 feed 拒绝请求或返回重定向，请检查入口与权限')
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ConfigurationError('公众号 feed 响应超过 16 MiB 限制')
                payload.extend(chunk)
            return payload.decode(response.encoding or 'utf-8', errors='replace')
    except httpx.TransportError as exc:
        raise TransientCollectionError('公众号 feed 连接/读取失败') from exc


async def wechat_rss_batches(snapshot: dict[str, Any], checkpoint: dict[str, Any]) -> AsyncIterator[CollectionBatch]:
    from app.intelligence.services.collection import CollectionBatch, ConfigurationError  # noqa: PLC0415

    validate_wechat_rss_config(snapshot)
    config = snapshot['config']
    feed_url = config['feed_url']
    async with _make_client(config) as client:
        xml_text = await _fetch_feed(client, feed_url)
    try:
        account, _bizid, items = _parse_feed(xml_text, feed_url, config.get('limit', DEFAULT_LIMIT))
    except (ET.ParseError, ValueError) as exc:
        raise ConfigurationError('公众号 RSS 结构无效，不能将解析失败作为空采集成功') from exc
    records = [record for item in items if (record := _to_record(account, item)) is not None]
    yield CollectionBatch(records, {})
