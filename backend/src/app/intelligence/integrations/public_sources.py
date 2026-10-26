"""公开科技情报来源的网络抓取与解析适配器。"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

_USER_AGENT = 'PipeSight/1.0 (+local research platform)'
_PIPECHINA_HOME = 'https://www.pipechina.com.cn'
DEFAULT_PIPECHINA_ENDPOINT = f'{_PIPECHINA_HOME}/groupnews.html'
DEFAULT_CROSSREF_ENDPOINT = 'https://api.crossref.org/works'


def _clean_text(value: str) -> str:
    value = re.sub(r'<script\b[^>]*>.*?</script>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<style\b[^>]*>.*?</style>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def _fetch_text(url: str, *, accept: str = 'text/html') -> str:
    request = Request(url, headers={'User-Agent': _USER_AGENT, 'Accept': accept})
    with urlopen(request, timeout=25) as response:
        payload = response.read()
        charset = response.headers.get_content_charset() or 'utf-8'
    return payload.decode(charset, errors='replace')


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r'(20\d{2})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?', value)
    if not match:
        return None
    year, month, day = match.groups()
    return datetime(int(year), int(month), int(day or 1))


def _parse_pipechina_index(source_html: str, endpoint: str, limit: int) -> list[dict]:
    rows: list[dict] = []
    link_pattern = re.compile(
        r'<a\b[^>]*href=["\'](?P<href>/front/news/\d+\.html)["\'][^>]*>(?P<label>.*?)</a>',
        flags=re.I | re.S,
    )
    markers = [match.start() for match in re.finditer(r'class=["\'](?:item|li)["\']', source_html)]
    for match in link_pattern.finditer(source_html):
        if len(rows) >= limit:
            break
        start = max((marker for marker in markers if marker < match.start()), default=max(0, match.start() - 2500))
        next_markers = [marker for marker in markers if marker > start]
        end = min(next_markers[0] if next_markers else len(source_html), match.end() + 1800)
        block = source_html[start:end]
        title_match = re.search(r'\btitle=["\']([^"\']+)["\']', match.group(0), flags=re.I)
        title = html.unescape(title_match.group(1) if title_match else _clean_text(match.group('label')))
        date_match = re.search(r'20\d{2}[.\-/]\d{1,2}(?:[.\-/]\d{1,2})?', block)
        summary_match = re.search(r'class=["\']desc["\'][^>]*>(.*?)</div>', block, flags=re.I | re.S)
        summary = _clean_text(summary_match.group(1)) if summary_match else ''
        canonical_url = urljoin(endpoint, match.group('href'))
        rows.append(
            {
                'title': title[:500],
                'url': canonical_url,
                'summary': summary[:400],
                'published_time': _parse_date(date_match.group(0) if date_match else None),
            }
        )
    return rows


def _parse_pipechina_detail(url: str) -> dict:
    source_html = _fetch_text(url)
    title_match = re.search(r'<div class=["\']title[^>]*>(.*?)</div>', source_html, flags=re.I | re.S)
    date_match = re.search(r'<span class=["\']span3["\'][^>]*>(.*?)</span>', source_html, flags=re.I | re.S)
    meta_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', source_html, flags=re.I | re.S)
    content_match = re.search(r'class=["\']text\s+content_class["\'][^>]*>(.*?)</div>', source_html, flags=re.I | re.S)
    body = _clean_text(content_match.group(1)) if content_match else ''
    summary = html.unescape(meta_match.group(1)).strip() if meta_match else body[:400]
    return {
        'title': _clean_text(title_match.group(1))[:500] if title_match else '',
        'summary': summary[:1000],
        'body': body[:2_000_000],
        'published_time': _parse_date(_clean_text(date_match.group(1)) if date_match else None),
    }


def collect_pipechina_records(endpoint: str, config: dict) -> list[dict]:
    """抓取并解析国家管网集团要闻。"""
    limit = min(max(int(config.get('limit', 12)), 1), 30)
    index_endpoint = endpoint or DEFAULT_PIPECHINA_ENDPOINT
    index_html = _fetch_text(index_endpoint)
    candidates = _parse_pipechina_index(index_html, index_endpoint, limit)
    records = []
    for candidate in candidates:
        try:
            detail = _parse_pipechina_detail(candidate['url'])
        except Exception:
            detail = {}
        records.append({**candidate, **detail, 'url': candidate['url'], 'title': detail.get('title') or candidate['title']})
    return records


def collect_crossref_records(endpoint: str, config: dict) -> list[dict]:
    """抓取并解析 Crossref 管道论文。"""
    rows = min(max(int(config.get('limit', 12)), 1), 25)
    query = str(config.get('query') or 'oil gas pipeline integrity monitoring')
    params = f'?query={quote_plus(query)}&filter=from-pub-date:2022-01-01,type:journal-article&rows={rows}&select=DOI,title,author,published,container-title,publisher,abstract,URL'
    request_url = f'{endpoint or DEFAULT_CROSSREF_ENDPOINT}{params}'
    payload = json.loads(_fetch_text(request_url, accept='application/json'))
    records = []
    for item in payload.get('message', {}).get('items', []):
        title = str((item.get('title') or [''])[0]).strip()
        doi = str(item.get('DOI') or '').strip()
        if not title or not doi:
            continue
        published = item.get('published', {}).get('date-parts', [[]])[0]
        year = int(published[0]) if published else None
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get('author', [])]
        abstract = _clean_text(str(item.get('abstract') or ''))
        records.append(
            {
                'title': title[:500],
                'url': item.get('URL') or f'https://doi.org/{doi}',
                'doi': doi,
                'authors': authors[:50],
                'authors_text': ', '.join(authors)[:1000],
                'journal': str((item.get('container-title') or [''])[0])[:255],
                'publisher': str(item.get('publisher') or '')[:255],
                'publication_year': year,
                'abstract': abstract[:2_000_000],
            }
        )
    return records


__all__ = ['DEFAULT_CROSSREF_ENDPOINT', 'DEFAULT_PIPECHINA_ENDPOINT', 'collect_crossref_records', 'collect_pipechina_records']
