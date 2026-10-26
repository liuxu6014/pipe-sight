"""采集正文写入新内容契约；内容、计数和断点在同一事务提交。"""

import hashlib
import re
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError

from app.business_ids import parse_business_id
from app.intelligence.repositories.collection_repository import CollectionRepository


def canonical_url(value):
    if not isinstance(value, str):
        raise ValueError('内容 URL 必须为文本')
    parts = urlsplit((value or '').strip())
    if parts.scheme.lower() not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('无效内容 URL')
    host = parts.hostname.lower()
    port = parts.port
    if ':' in host:
        host = f'[{host}]'
    if port and (parts.scheme.lower(), port) not in (('http', 80), ('https', 443)):
        host += f':{port}'
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')
    )
    return urlunsplit((parts.scheme.lower(), host, parts.path or '/', urlencode(query), ''))


def normalize_doi(value):
    if value is not None and not isinstance(value, str):
        raise ValueError('DOI 必须为文本')
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', (value or '').strip(), flags=re.I).lower()
    if doi and not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
        raise ValueError('无效 DOI')
    return doi or None


def publication_date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value):
        raise ValueError('论文日期须保留真实 ISO 精度')
    date.fromisoformat(value + {4: '-01-01', 7: '-01', 10: ''}[len(value)])
    return value


class CollectionPersistenceService:
    @staticmethod
    async def save_record(db, source, record, now, *, category_id=None):
        # Lazy import permits main-agent content-model integration without importing
        # retired processing/review/model-route modules in the worker.
        from app.intelligence.models.content import PipelineArticle, PipelinePaper

        if category_id is not None:
            category_id = parse_business_id(category_id)

        if not isinstance(record, dict):
            raise ValueError('候选条目必须为对象')
        for key in ('author', 'content', 'content_zh', 'title_zh', 'authors', 'journal', 'abstract', 'abstract_zh'):
            if record.get(key) is not None and not isinstance(record[key], str):
                raise ValueError('候选文本字段类型无效')
        title = record.get('title')
        if not isinstance(title, str) or not title.strip() or len(title) > 1000:
            raise ValueError('标题无效')
        url = canonical_url(record['url']) if record.get('url') else None
        if source.type == 'paper':
            model = PipelinePaper
            doi = normalize_doi(record.get('doi'))
            if not doi and not url:
                raise ValueError('论文必须有 DOI 或 URL')
            # DOI and fallback URL must not resolve to two distinct papers.
            filters = [model.doi == doi] if doi else []
            if url:
                filters.append(model.url == url)
            values = {key: record.get(key) for key in ('title_zh', 'authors', 'journal', 'abstract', 'abstract_zh')}
            values.update(
                title=title.strip(), doi=doi, url=url, published_date=publication_date(record.get('published_date'))
            )
            locks = [f'doi:{doi}'] if doi else []
            if url:
                locks.append(f'paper-url:{url}')
        elif source.type in ('website', 'wechat'):
            if not url:
                raise ValueError('新闻必须有 URL')
            model, filters, locks = PipelineArticle, [PipelineArticle.url == url], [f'article-url:{url}']
            published = record.get('published_at')
            if published is not None:
                if isinstance(published, str):
                    published = datetime.fromisoformat(published.replace('Z', '+00:00'))
                if not isinstance(published, datetime) or published.tzinfo is None:
                    raise ValueError('发布时间必须为真实带时区时间点')
            values = {key: record.get(key) for key in ('author', 'content', 'content_zh')}
            values.update(title=title.strip(), url=url, published_at=published)
        else:
            raise ValueError('来源内容类型无效')
        # Serializes normalized-identity writes across different source workers.
        if db.get_bind().dialect.name == 'postgresql':
            for key in sorted(locks):
                number = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big', signed=True)
                await db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': number})
        matches = list((await db.execute(select(model).where(or_(*filters)).with_for_update())).scalars().all())
        if len(matches) > 1:
            raise ValueError('DOI 与 URL 对应不同历史论文，需核对')
        existing = matches[0] if matches else None
        if existing:
            # Preserve existing category, source identity and push receipt.
            if all(getattr(existing, key) == value for key, value in values.items()) and (
                category_id is None or existing.category_id == category_id
            ):
                return 0
            for key, value in values.items():
                setattr(existing, key, value)
            existing.updated_at = now
            if category_id is not None:
                existing.category_id = category_id
        else:
            db.add(
                model(
                    source_id=source.id,
                    category_id=category_id,
                    is_pushed=False,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
            )
        await db.flush()
        return 1

    @classmethod
    async def save_batch(
        cls, db, run_id, token, records, checkpoint, *, now, supports_resume=False, clock=None, classifications=None
    ):
        try:
            source, run = await CollectionRepository.locked_run(db, run_id)
            CollectionRepository.fence(run, token, now)
            # Source configuration may have changed since enqueueing.
            from types import SimpleNamespace

            frozen_source = SimpleNamespace(id=source.id, type=run.config_snapshot['type'])
            saved = failed = 0
            if classifications is not None and len(classifications) != len(records):
                raise ValueError('分类结果必须与候选条目一一对应')
            for index, record in enumerate(records):
                category_id, classification_failed = (
                    classifications[index] if classifications is not None else (None, False)
                )
                if classification_failed:
                    failed += 1
                    run.error = '候选条目分类失败，请检查后台类别模型后重试'
                    continue
                try:
                    async with db.begin_nested():
                        if category_id is not None:
                            category_id = parse_business_id(category_id)
                            from app.intelligence.models.content import PipelineCategory

                            category = (
                                (
                                    await db.execute(
                                        select(PipelineCategory).where(
                                            PipelineCategory.id == category_id,
                                            PipelineCategory.is_enabled.is_(True),
                                            PipelineCategory.applies_to.in_(
                                                ['paper' if frozen_source.type == 'paper' else 'news', 'all']
                                            ),
                                        )
                                    )
                                )
                                .scalars()
                                .first()
                            )
                            if category is None:
                                raise ValueError('分类结果已停用或不适用于该内容类型')
                        saved += await cls.save_record(db, frozen_source, record, now, category_id=category_id)
                except (ValueError, TypeError, KeyError, IntegrityError):
                    failed += 1
            run.fetched_count += len(records)
            run.saved_count += saved
            run.failed_count += failed
            # A single unresolved item invalidates continuation beyond it. Resume
            # starts from the entry on retry, with URL/DOI idempotency.
            run.checkpoint = checkpoint if supports_resume and not run.failed_count else {}
            committed_at = (clock or (lambda: datetime.now(timezone.utc)))()
            CollectionRepository.fence(run, token, committed_at)
            run.updated_at = committed_at
            await db.commit()
            return saved, failed
        except BaseException:
            await db.rollback()
            raise
