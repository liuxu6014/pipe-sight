from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import or_, select

from module_pipeline.entity.do.pipeline_do import PipelineArticle, PipelineCrawlRun, PipelinePaper, PipelineSource
from module_pipeline.service.pipeline_prompt_service import PipelinePromptService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_USER_AGENT = 'PipeSight/1.0 (+local research platform)'
_PIPECHINA_HOME = 'https://www.pipechina.com.cn'
_DEFAULT_PIPECHINA_ENDPOINT = f'{_PIPECHINA_HOME}/groupnews.html'
_DEFAULT_CROSSREF_ENDPOINT = 'https://api.crossref.org/works'


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


def _pipechina_records(endpoint: str, config: dict) -> list[dict]:
    limit = min(max(int(config.get('limit', 12)), 1), 30)
    index_html = _fetch_text(endpoint or _DEFAULT_PIPECHINA_ENDPOINT)
    candidates = _parse_pipechina_index(index_html, endpoint or _DEFAULT_PIPECHINA_ENDPOINT, limit)
    records = []
    for candidate in candidates:
        try:
            detail = _parse_pipechina_detail(candidate['url'])
        except Exception:
            detail = {}
        records.append({**candidate, **detail, 'url': candidate['url'], 'title': detail.get('title') or candidate['title']})
    return records


def _crossref_records(endpoint: str, config: dict) -> list[dict]:
    rows = min(max(int(config.get('limit', 12)), 1), 25)
    query = str(config.get('query') or 'oil gas pipeline integrity monitoring')
    params = f'?query={quote_plus(query)}&filter=from-pub-date:2022-01-01,type:journal-article&rows={rows}&select=DOI,title,author,published,container-title,publisher,abstract,URL'
    request_url = f'{endpoint or _DEFAULT_CROSSREF_ENDPOINT}{params}'
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


def _score(text: str) -> int:
    keywords = ('管道', '油气', 'pipeline', 'integrity', 'monitoring', '天然气', '能源')
    hits = sum(1 for keyword in keywords if keyword.lower() in text.lower())
    return min(98, 68 + hits * 5)


class PipelineCollectionService:
    """真实公开来源采集器，所有运行都会写入 collection_runs 便于追溯。"""

    @classmethod
    async def ensure_real_sources(cls, db: AsyncSession) -> list[PipelineSource]:
        definitions = [
            {
                'source_id': 'src-pipechina',
                'source_code': 'pipechina-group-news',
                'name': '国家管网集团要闻',
                'source_type': 'news',
                'endpoint': _DEFAULT_PIPECHINA_ENDPOINT,
                'adapter_key': 'pipechina_group_news',
                'schedule_cron': '0 */6 * * *',
                'config_json': {'limit': 12, 'trust': 'official'},
            },
            {
                'source_id': 'src-crossref',
                'source_code': 'crossref-pipeline-papers',
                'name': 'Crossref 管道论文',
                'source_type': 'paper',
                'endpoint': _DEFAULT_CROSSREF_ENDPOINT,
                'adapter_key': 'crossref_works',
                'schedule_cron': '0 3 * * *',
                'config_json': {'limit': 12, 'query': 'oil gas pipeline integrity monitoring'},
            },
        ]
        sources: list[PipelineSource] = []
        for definition in definitions:
            source = (
                await db.execute(select(PipelineSource).where(PipelineSource.source_code == definition['source_code']))
            ).scalars().first()
            if not source:
                source = PipelineSource(**definition)
                db.add(source)
            else:
                for key, value in definition.items():
                    if key != 'source_id':
                        setattr(source, key, value)
                source.enabled = True
                source.status = 'active'
            sources.append(source)
        await db.flush()
        return sources

    @classmethod
    async def collect_source(  # noqa: PLR0915
        cls, db: AsyncSession, source: PipelineSource, *, trigger_type: str = 'manual'
    ) -> dict:
        source_id = source.source_id
        source_name = source.name
        adapter_key = source.adapter_key
        endpoint = source.endpoint
        config = dict(source.config_json or {})
        prompt_snapshot = await PipelinePromptService.get_published_snapshot(db, 'data-filter')
        if prompt_snapshot:
            config['filterPrompt'] = prompt_snapshot
        now = datetime.now()
        run = PipelineCrawlRun(
            run_id=f'run-{uuid4().hex[:16]}',
            source_id=source_id,
            trigger_type=trigger_type,
            status='running',
            config_snapshot=config,
            started_at=now,
            create_time=now,
            update_time=now,
        )
        db.add(run)
        source.last_run_time = now
        source.last_run_status = 'running'
        run_id = run.run_id
        await db.commit()
        source = (await db.execute(select(PipelineSource).where(PipelineSource.source_id == source_id))).scalars().one()
        run = (await db.execute(select(PipelineCrawlRun).where(PipelineCrawlRun.run_id == run_id))).scalars().one()
        try:
            if adapter_key == 'pipechina_group_news':
                records = await asyncio.to_thread(_pipechina_records, endpoint or _DEFAULT_PIPECHINA_ENDPOINT, config)
                inserted, updated, duplicate = await cls._save_articles(db, source, run, records)
            elif adapter_key == 'crossref_works':
                records = await asyncio.to_thread(_crossref_records, endpoint or _DEFAULT_CROSSREF_ENDPOINT, config)
                inserted, updated, duplicate = await cls._save_papers(db, source, run, records)
            else:
                raise ValueError(f'未注册的采集适配器：{adapter_key}')
            run.status = 'success'
            run.fetched_count = len(records)
            run.inserted_count = inserted
            run.updated_count = updated
            run.duplicate_count = duplicate
            run.finished_at = datetime.now()
            run.update_time = datetime.now()
            source.last_run_status = 'success'
            source.success_count = (source.success_count or 0) + 1
            source.consecutive_failures = 0
            await db.commit()
            return {'run_id': run_id, 'source': source_name, 'status': 'success', 'fetched': len(records), 'inserted': inserted, 'updated': updated, 'duplicates': duplicate}
        except Exception as exc:
            await db.rollback()
            run = (await db.execute(select(PipelineCrawlRun).where(PipelineCrawlRun.run_id == run_id))).scalars().first()
            source = (await db.execute(select(PipelineSource).where(PipelineSource.source_id == source_id))).scalars().first()
            run.status = 'failed'
            run.failed_count = 1
            run.error_message = str(exc)[:2000]
            run.finished_at = datetime.now()
            run.update_time = datetime.now()
            source.last_run_status = 'failed'
            source.failure_count = (source.failure_count or 0) + 1
            source.consecutive_failures = (source.consecutive_failures or 0) + 1
            await db.commit()
            raise

    @classmethod
    async def _save_articles(cls, db: AsyncSession, source: PipelineSource, run: PipelineCrawlRun, records: list[dict]) -> tuple[int, int, int]:
        inserted = updated = duplicate = 0
        for record in records:
            url = record['url']
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            body = record.get('body') or record.get('summary') or ''
            article_hash = hashlib.sha256(body.encode()).hexdigest()
            existing = (
                await db.execute(
                    select(PipelineArticle).where(
                        or_(PipelineArticle.url_hash == url_hash, PipelineArticle.article_hash == article_hash)
                    )
                )
            ).scalars().first()
            values = {
                'title': record['title'], 'canonical_url': url, 'source_id': source.source_id,
                'source_name': source.name, 'collection_run_id': run.run_id,
                'published_time': record.get('published_time') or datetime.now(),
                'summary': record.get('summary') or body[:400], 'body': body,
                'url_hash': url_hash, 'article_hash': article_hash,
                'relevance_score': _score(f"{record['title']} {body}"), 'tags': ['国家管网', '管网科技', '公开资讯'],
                'metadata_json': {'collector': source.adapter_key, 'canonicalUrl': url}, 'update_time': datetime.now(),
            }
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                duplicate += 1
                updated += 1
            else:
                db.add(PipelineArticle(article_id=f'article-{uuid4().hex[:16]}', article_type='news', permission_scope='public', handoff_status='pending', handoff_result_json={}, version_no=1, discovered_time=datetime.now(), create_time=datetime.now(), **values))
                inserted += 1
        await db.flush()
        return inserted, updated, duplicate

    @classmethod
    async def _save_papers(cls, db: AsyncSession, source: PipelineSource, run: PipelineCrawlRun, records: list[dict]) -> tuple[int, int, int]:
        inserted = updated = duplicate = 0
        for record in records:
            doi = record['doi'].lower().removeprefix('https://doi.org/')
            existing = (await db.execute(select(PipelinePaper).where(PipelinePaper.doi_normalized == doi))).scalars().first()
            values = {
                'title': record['title'], 'canonical_url': record['url'], 'source_id': source.source_id,
                'source_name': source.name, 'collection_run_id': run.run_id, 'authors': record.get('authors_text'),
                'authors_json': record.get('authors') or [], 'doi': record['doi'], 'doi_normalized': doi,
                'external_id': doi, 'journal': record.get('journal'), 'publisher': record.get('publisher'),
                'publication_year': record.get('publication_year'), 'abstract_text': record.get('abstract') or '',
                'full_text_url': record['url'], 'citation_count': 0,
                'tags': ['管道完整性', '油气管网', '公开论文'],
                'metadata_json': {'collector': source.adapter_key, 'relevanceScore': _score(record['title'])}, 'update_time': datetime.now(),
            }
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                duplicate += 1
                updated += 1
            else:
                db.add(PipelinePaper(paper_id=f'paper-{uuid4().hex[:16]}', permission_scope='public', review_status='pending', handoff_status='pending', handoff_result_json={}, open_access_status='unknown', full_text_status='unknown', create_time=datetime.now(), **values))
                inserted += 1
        await db.flush()
        return inserted, updated, duplicate
