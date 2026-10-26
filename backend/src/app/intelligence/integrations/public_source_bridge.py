"""Bridge the existing public_sources collectors to cancellable async batches.

Keeps their adapter IDs, endpoints, index/text parsing and Crossref query policy.
The blocking urllib orchestration is replaced, never sent to a background thread.
Index/offset positions aren't stable snapshots, so both adapters restart from the
entry after failure and rely on the content repository's URL/DOI idempotency.
Importing/registering this module performs no network I/O and creates no sources.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.intelligence.integrations.public_sources import (
    DEFAULT_CROSSREF_ENDPOINT,
    DEFAULT_PIPECHINA_ENDPOINT,
    _clean_text,
    _parse_pipechina_index,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.intelligence.services.collection import AdapterRegistry, CollectionBatch

PIPECHINA_HOSTS = ('www.pipechina.com.cn',)
CROSSREF_HOSTS = ('api.crossref.org',)
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
CROSSREF_SELECT = 'DOI,title,author,published,container-title,publisher,abstract,URL'
COMMON_CONFIG = {'limit', 'request_timeout', 'total_timeout', 'retry', 'request_interval'}


def validate_adapter_config(snapshot: dict[str, Any]) -> None:
    """Validate before enqueue/enable, not after the first network request."""
    from app.intelligence.services.collection import ConfigurationError

    config = snapshot['config']
    paper = snapshot['adapter'] == 'crossref_works'
    allowed = COMMON_CONFIG | ({'query', 'batch_size'} if paper else set())
    if set(config) - allowed:
        raise ConfigurationError('此公开适配器含不支持的采集配置，请核对来源设置')
    limit = config.get('limit', 12)
    maximum = 30
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise ConfigurationError(f'采集 limit 必须为 1～{maximum} 的整数')
    interval = config.get('request_interval', 0)
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0 <= interval <= 60:
        raise ConfigurationError('request_interval 必须为 0～60 秒')
    if paper:
        size = config.get('batch_size', 5)
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 25:
            raise ConfigurationError('Crossref batch_size 必须为 1～25 的整数')
        query = config.get('query') or 'oil gas pipeline integrity monitoring'
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ConfigurationError('Crossref query 必须为非空文本且不超过 1000 字符')
    endpoint = snapshot.get('url') or (DEFAULT_CROSSREF_ENDPOINT if paper else DEFAULT_PIPECHINA_ENDPOINT)
    validate_url(endpoint, CROSSREF_HOSTS if paper else PIPECHINA_HOSTS)
    parts = urlsplit(endpoint)
    if parts.query or parts.fragment or (paper and parts.path != '/works'):
        raise ConfigurationError('来源入口不允许附带查询/片段；Crossref 入口须为 /works')


def validate_url(url: str, hosts: tuple[str, ...]) -> None:
    from app.intelligence.services.collection import ConfigurationError

    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == 'https'
            and parsed.hostname in hosts
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
        )
    except (ValueError, TypeError) as exc:
        raise ConfigurationError('公开采集地址无效') from exc
    if not valid:
        raise ConfigurationError('公开采集地址超出固定 HTTPS 来源范围')


def make_client(config: dict[str, Any]) -> httpx.AsyncClient:
    seconds = config.get('request_timeout', 30)
    return httpx.AsyncClient(
        timeout=httpx.Timeout(seconds, connect=min(seconds, 10)),
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        headers={'User-Agent': 'PipeSight/1.0 (+local research platform)'},
    )


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    hosts: tuple[str, ...],
    *,
    params: dict[str, Any] | None = None,
    accept: str = 'text/html',
) -> str:
    from app.intelligence.services.collection import ConfigurationError, TransientCollectionError

    validate_url(url, hosts)
    try:
        async with client.stream('GET', url, params=params, headers={'Accept': accept}) as response:
            if response.status_code in (408, 429) or response.status_code >= 500:
                raise TransientCollectionError('公开端点临时不可用')
            if response.status_code != 200:
                # Redirects aren't followed (including a redirect to an internal
                # address). Access/configuration failures must be fixed explicitly.
                raise ConfigurationError('公开端点拒绝请求或返回重定向，请检查入口与权限')
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ConfigurationError('公开端点响应超过 4 MiB 限制')
                payload.extend(chunk)
            return payload.decode(response.encoding or 'utf-8', errors='replace')
    except httpx.TransportError as exc:
        raise TransientCollectionError('公开端点连接/读取失败') from exc


def parse_pipechina_detail(source_html: str) -> dict[str, Any]:
    """The existing detail parser's selectors, now separated from urllib I/O."""
    title = re.search(r'<div class=["\']title[^>]*>(.*?)</div>', source_html, flags=re.I | re.S)
    content = re.search(r'class=["\']text\s+content_class["\'][^>]*>(.*?)</div>', source_html, flags=re.I | re.S)
    published = re.search(r'<span class=["\']span3["\'][^>]*>(.*?)</span>', source_html, flags=re.I | re.S)
    stamp = re.search(
        r'(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?',
        _clean_text(published.group(1)) if published else '',
    )
    published_at = None
    if stamp:
        try:
            published_at = datetime(*(int(value or 0) for value in stamp.groups()), tzinfo=ZoneInfo('Asia/Shanghai'))
        except ValueError:
            pass  # Unknown/invalid dates never become the ingestion timestamp.
    return {
        'title': _clean_text(title.group(1))[:1000] if title else None,
        'content': _clean_text(content.group(1))[:2_000_000] if content else None,
        'published_at': published_at,
        'author': None,
    }


async def pipechina_batches(snapshot: dict[str, Any], checkpoint: dict[str, Any]) -> AsyncIterator[CollectionBatch]:
    from app.intelligence.services.collection import CollectionBatch, ConfigurationError

    validate_adapter_config(snapshot)
    config = snapshot['config']
    endpoint = snapshot.get('url') or DEFAULT_PIPECHINA_ENDPOINT
    async with make_client(config) as client:
        index = await fetch_text(client, endpoint, PIPECHINA_HOSTS)
        candidates = _parse_pipechina_index(index, endpoint, config.get('limit', 12))
        if not candidates and not re.fullmatch(
            r'(?:暂无(?:数据|内容|新闻)|no\s+(?:news|results))[。！!.]?', _clean_text(index), re.I
        ):
            raise ConfigurationError('国家管网索引结构无效，不能将解析失败作为空采集成功')
        # Yield between the index request and the first detail request: every
        # potentially slow HTTP operation has a stop/heartbeat/timeout boundary.
        yield CollectionBatch([], {})
        for candidate in candidates:
            await asyncio.sleep(config.get('request_interval', 0))
            page = await fetch_text(client, candidate['url'], PIPECHINA_HOSTS)
            detail = parse_pipechina_detail(page)
            if not detail['title'] and detail['content'] is None:
                raise ConfigurationError('国家管网详情结构无效，需核对页面后修复适配器')
            detail.update(url=candidate['url'], title=detail['title'] or candidate['title'])
            # Never substitute an index summary for a detail body or silently
            # report a failed detail request as successful collection.
            yield CollectionBatch([detail], {})


def parse_crossref_item(item: Any) -> dict[str, Any]:
    """Existing Crossref metadata mapping plus the real partial publication date."""
    if not isinstance(item, dict):
        return {}  # A malformed candidate is counted failed by persistence.
    titles = item.get('title') or []
    title = str(titles[0]).strip() if isinstance(titles, list) and titles else None
    doi = str(item.get('DOI') or '').strip() or None
    names = [
        f'{author.get("given", "")} {author.get("family", "")}'.strip()
        for author in (item.get('author') or [])
        if isinstance(author, dict)
    ]
    parts = (item.get('published') or {}).get('date-parts') or []
    published_date = None
    if parts and isinstance(parts[0], list) and 1 <= len(parts[0]) <= 3:
        values = parts[0]
        if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            try:
                date(values[0], values[1] if len(values) > 1 else 1, values[2] if len(values) > 2 else 1)
                published_date = '-'.join(
                    f'{value:04d}' if index == 0 else f'{value:02d}' for index, value in enumerate(values)
                )
            except ValueError:
                pass
    journals = item.get('container-title') or []
    return {
        'title': title,
        'url': item.get('URL') or (f'https://doi.org/{doi}' if doi else None),
        'doi': doi,
        'authors': ', '.join(name for name in names[:50] if name) or None,
        'journal': str(journals[0])[:255] if isinstance(journals, list) and journals else None,
        'published_date': published_date,
        'abstract': _clean_text(str(item.get('abstract') or ''))[:2_000_000] or None,
    }


async def crossref_batches(snapshot: dict[str, Any], checkpoint: dict[str, Any]) -> AsyncIterator[CollectionBatch]:
    from app.intelligence.services.collection import CollectionBatch, ConfigurationError

    validate_adapter_config(snapshot)
    config = snapshot['config']
    limit, offset = config.get('limit', 12), 0
    endpoint = snapshot.get('url') or DEFAULT_CROSSREF_ENDPOINT
    async with make_client(config) as client:
        while offset < limit:
            await asyncio.sleep(config.get('request_interval', 0))
            rows = min(config.get('batch_size', 5), limit - offset)
            # Keep the existing collector's query/filter/select semantics.
            params = {
                'query': config.get('query') or 'oil gas pipeline integrity monitoring',
                'filter': 'from-pub-date:2022-01-01,type:journal-article',
                'rows': rows,
                'offset': offset,
                'select': CROSSREF_SELECT,
            }
            response = await fetch_text(client, endpoint, CROSSREF_HOSTS, params=params, accept='application/json')
            try:
                payload = json.loads(response)
                items = payload['message']['items']
                if not isinstance(items, list) or len(items) > rows:
                    raise ValueError('Invalid page size')
            except (ValueError, KeyError, TypeError) as exc:
                raise ConfigurationError('Crossref 响应结构无效，未冒充空采集成功') from exc
            if not items:
                break
            yield CollectionBatch([parse_crossref_item(item) for item in items], {})
            offset += len(items)
            if len(items) < rows:
                break


def register_builtin_adapters(registry: AdapterRegistry) -> None:
    from app.intelligence.services.collection import Adapter

    registry.register(
        'pipechina_group_news',
        Adapter(pipechina_batches, ('website',), PIPECHINA_HOSTS, validate_config=validate_adapter_config),
    )
    registry.register(
        'crossref_works', Adapter(crossref_batches, ('paper',), CROSSREF_HOSTS, validate_config=validate_adapter_config)
    )
