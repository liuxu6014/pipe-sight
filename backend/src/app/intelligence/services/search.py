"""统一搜索读模型。"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.business_ids import parse_business_id, wire_id
from app.intelligence.repositories.content_repository import ContentDao as PipelineDao
from app.intelligence.repositories.content_repository import SearchCursor
from app.intelligence.services.catalog import IntelligenceCatalogService
from exceptions.exception import ServiceException

SEARCH_CURSOR_VERSION = 3


class IntelligenceSearchService:
    """在数据库侧按权限检索公开情报和用户自己的内部资料。"""

    _max_page_num = 100
    _content_types = frozenset({'all', 'news', 'website', 'wechat', 'paper', 'document', 'report', 'evidence'})
    _sources = frozenset({'all', 'public', 'internal'})
    _date_ranges = frozenset({'all', 'week', 'year'})

    @staticmethod
    def _search_rank(keyword: str | None, *values: Any) -> int:
        term = (keyword or '').strip().casefold()
        if not term:
            return 0
        for index, value in enumerate(values):
            if term in str(value or '').casefold():
                return len(values) - index
        return 0

    @staticmethod
    def _cursor_context(
        user_id: int,
        keyword: str | None,
        content_type: str,
        source: str,
        date_range: str,
        directions: list[str],
    ) -> str:
        context = {
            'version': SEARCH_CURSOR_VERSION,
            'user_id': user_id,
            'keyword': (keyword or '').strip().casefold(),
            'content_type': content_type,
            'source': source,
            'date_range': date_range,
            'directions': sorted(set(directions)),
        }
        serialized = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    @staticmethod
    def _encode_cursor(row: dict[str, Any], *, context: str) -> str:
        payload = {
            'v': SEARCH_CURSOR_VERSION,
            'context': context,
            'score': int(row.get('_search_rank') or 0),
            'date': row.get('_cursor_date') or datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat(),
            'type': str(row.get('type') or ''),
            'id': wire_id(row['id']),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode()
        return encoded.rstrip('=')

    @staticmethod
    def _decode_cursor(value: str | None, *, expected_context: str) -> SearchCursor | None:
        if not value:
            return None
        try:
            padded = value + ('=' * (-len(value) % 4))
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            if payload.get('v') != SEARCH_CURSOR_VERSION or payload.get('context') != expected_context:
                raise ValueError('unsupported cursor version')
            score = payload['score']
            if type(score) is not int or score < 0:
                raise ValueError('invalid cursor score')
            published_at = datetime.fromisoformat(payload['date'])
            if published_at.tzinfo is None:
                raise ValueError('cursor instant requires timezone')
            published_at = published_at.astimezone(timezone.utc)
            content_type = payload['type']
            item_id = parse_business_id(payload['id'])
            if content_type not in {'news', 'paper', 'document', 'report'} or not item_id:
                raise ValueError('invalid cursor identity')
            return score, published_at, content_type, item_id
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            raise ServiceException(message='搜索游标无效，请重新搜索') from None

    @staticmethod
    def _normalize_directions(value: str | None) -> list[str]:
        return [item.strip() for item in (value or '').split(',') if item.strip()]

    @staticmethod
    def _sort_key(row: dict[str, Any], keyword: str | None = None) -> tuple[int, datetime, str, int]:
        """为跨类型合并结果提供相关性优先且稳定的降序排序键。"""
        relevance = int(row.get('_search_rank') or 0)
        instant = (
            datetime.fromisoformat(row['_cursor_date'])
            if row.get('_cursor_date')
            else datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        return (
            relevance,
            instant.astimezone(timezone.utc),
            row.get('type') or '',
            parse_business_id(row['id']),
        )

    @staticmethod
    def _highlight_parts(text: str | None, keyword: str | None) -> list[dict[str, Any]]:
        """返回安全的文本片段，不返回可直接执行的 HTML。"""
        value = str(text or '')
        term = (keyword or '').strip()
        if not term:
            return [{'text': value, 'match': False}] if value else []
        parts: list[dict[str, Any]] = []
        cursor = 0
        for match in re.finditer(re.escape(term), value, flags=re.IGNORECASE):
            if match.start() > cursor:
                parts.append({'text': value[cursor : match.start()], 'match': False})
            parts.append({'text': match.group(0), 'match': True})
            cursor = match.end()
        if cursor < len(value):
            parts.append({'text': value[cursor:], 'match': False})
        return parts or [{'text': value, 'match': False}]

    @classmethod
    def _snippet_parts(
        cls,
        summary: Any,
        fallback: Any,
        keyword: str | None,
        *,
        max_length: int = 240,
    ) -> list[dict[str, Any]]:
        """截取命中上下文，避免用整段正文填满搜索结果。"""
        summary_text = str(summary or '')
        fallback_text = str(fallback or '')
        term = (keyword or '').strip()
        if term:
            folded_term = term.casefold()
            if folded_term in summary_text.casefold():
                value = summary_text
            elif folded_term in fallback_text.casefold():
                value = fallback_text
            else:
                value = summary_text or fallback_text
        else:
            value = summary_text or fallback_text
        if not value:
            return []
        if len(value) <= max_length or not term:
            clipped = value[:max_length].rstrip() if len(value) > max_length else value
            return cls._highlight_parts(f'{clipped}…' if len(value) > max_length else clipped, keyword)

        match = re.search(re.escape(term), value, flags=re.IGNORECASE)
        if not match:
            clipped = value[:max_length].rstrip()
            return cls._highlight_parts(f'{clipped}…', keyword)
        half_length = max_length // 2
        start = max(0, match.start() - half_length)
        end = min(len(value), start + max_length)
        start = max(0, end - max_length)
        prefix = '…' if start else ''
        suffix = '…' if end < len(value) else ''
        return cls._highlight_parts(f'{prefix}{value[start:end]}{suffix}', keyword)

    @staticmethod
    def _public_row(item: dict[str, Any], content_type: str) -> dict[str, Any]:
        if content_type == 'paper':
            return {
                'id': wire_id(item['id']),
                'type': 'paper',
                'type_label': '论文',
                'title': item['title'],
                'summary': item['summary'],
                'meta': f'{item["source"]} · {item["publish_time"]} · {item.get("doi") or "DOI待补充"}',
                'tags': item.get('tags', []),
                'source_kind': 'public',
                'published_at': item['publish_time'],
                'path': f'/portal/papers/{item["id"]}',
            }
        return {
            'id': wire_id(item['id']),
            'type': 'news',
            'type_label': '新闻资讯',
            'title': item['title'],
            'summary': item['summary'],
            'meta': f'{item["source"]} · {item["publish_time"]}',
            'tags': item.get('tags', []),
            'source_kind': 'public',
            'source_type': item.get('source_type', 'news'),
            'published_at': item['publish_time'],
            'path': f'/portal/news/{item["id"]}',
        }

    @staticmethod
    def _material_row(item: Any, date_formatter: Any) -> dict[str, Any]:
        return {
            'id': wire_id(item.id),
            'type': 'document',
            'type_label': '内部资料',
            'title': item.name,
            'parseStatus': item.status,
            'summary': (item.edited_text if item.edited_text is not None else item.extracted_text or '')[:240],
            'meta': '仅自己可见',
            'tags': [],
            'source_kind': 'internal',
            'published_at': date_formatter(item.updated_at),
            'path': f'/portal/knowledge/{item.id}',
        }

    @staticmethod
    def _report_row(item: Any, date_formatter: Any) -> dict[str, Any]:
        report_type = item.type
        return {
            'id': wire_id(item.id),
            'type': 'report',
            'type_label': '情报简报' if report_type in {'daily', 'weekly', 'monthly'} else '我的报告',
            'title': item.title,
            'summary': item.content[:240],
            'meta': f'V{item.version} · {date_formatter(item.updated_at)}',
            'tags': [report_type],
            'report_type': report_type,
            'source_kind': 'internal',
            'published_at': date_formatter(item.updated_at),
            'path': f'/portal/research/reports/{item.id}',
        }

    @classmethod
    def _decorate_row(
        cls,
        row: dict[str, Any],
        *,
        keyword: str | None,
        values: tuple[Any, ...],
        cursor_date: datetime | None,
        snippet_text: tuple[Any, Any] | None = None,
        sql_rank: int | None = None,
    ) -> dict[str, Any]:
        row['_search_rank'] = cls._search_rank(keyword, *values) if sql_rank is None else sql_rank
        normalized = cursor_date or datetime(1970, 1, 1, tzinfo=timezone.utc)
        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=timezone.utc)
        row['_cursor_date'] = normalized.astimezone(timezone.utc).isoformat()
        row['_snippet_text'] = snippet_text or (row.get('summary'), None)
        return row

    @classmethod
    async def search(  # noqa: PLR0912, PLR0913, PLR0915
        cls,
        db: Any,
        *,
        user_id: int,
        keyword: str | None,
        content_type: str,
        source: str,
        date_range: str,
        directions: str | None,
        page_num: int,
        page_size: int,
        date_formatter: Any,
        cursor: str | None = None,
        max_page_num: int | None = 100,
    ) -> dict[str, Any]:
        if content_type not in cls._content_types:
            raise ServiceException(message='不支持的搜索内容类型')
        if source not in cls._sources:
            raise ServiceException(message='不支持的搜索来源范围')
        if date_range not in cls._date_ranges:
            raise ServiceException(message='不支持的搜索时间范围')
        if max_page_num is not None and page_num > max_page_num:
            raise ServiceException(message='搜索页码不能超过100页，请缩小筛选范围')

        include_public = source in {'all', 'public'}
        include_internal = source in {'all', 'internal'}
        include_articles = include_public and content_type in {'all', 'evidence', 'news', 'website', 'wechat'}
        article_filters = (
            {'article_type': {'website': 'news', 'wechat': 'wechat'}[content_type]}
            if content_type in {'website', 'wechat'}
            else {}
        )
        include_papers = include_public and content_type in {'all', 'evidence', 'paper'}
        include_materials = include_internal and content_type in {'all', 'evidence', 'document'}
        include_reports = include_internal and content_type in {'all', 'report'}
        direction_terms = cls._normalize_directions(directions)
        cursor_context = cls._cursor_context(
            user_id,
            keyword,
            content_type,
            source,
            date_range,
            direction_terms,
        )
        search_after = cls._decode_cursor(cursor, expected_context=cursor_context)
        candidate_limit = page_size + 1 if search_after is not None else page_num * page_size
        date_to = datetime.now(timezone.utc) if date_range != 'all' else None
        date_from = date_to - timedelta(days=7 if date_range == 'week' else 365) if date_to else None
        rows: list[dict[str, Any]] = []
        counts = {'news': 0, 'paper': 0, 'document': 0, 'report': 0}

        if include_articles:
            articles = await PipelineDao.list_articles(
                db,
                ranked=True,
                **article_filters,
                keyword=keyword,
                published_from=date_from,
                published_to=date_to,
                directions=direction_terms,
                offset=0,
                limit=candidate_limit,
                **({'search_after': search_after} if search_after is not None else {}),
            )
            rows.extend(
                cls._decorate_row(
                    cls._public_row(
                        IntelligenceCatalogService.article_dict(item, date_formatter=date_formatter),
                        'article',
                    ),
                    keyword=keyword,
                    values=(item.title, item.content_zh, item.content, item.author),
                    cursor_date=getattr(item, '_search_cursor_date', item.published_at),
                    sql_rank=getattr(item, '_search_rank', None),
                    snippet_text=(item.content_zh, item.content),
                )
                for item in articles
            )
        if include_papers:
            papers = await PipelineDao.list_papers(
                db,
                ranked=True,
                keyword=keyword,
                published_from=date_from,
                published_to=date_to,
                directions=direction_terms,
                offset=0,
                limit=candidate_limit,
                **({'search_after': search_after} if search_after is not None else {}),
            )
            rows.extend(
                cls._decorate_row(
                    cls._public_row(
                        IntelligenceCatalogService.paper_dict(item, date_formatter=date_formatter),
                        'paper',
                    ),
                    keyword=keyword,
                    values=(item.title, item.title_zh, item.abstract_zh, item.abstract, item.authors),
                    sql_rank=getattr(item, '_search_rank', None),
                    cursor_date=getattr(item, '_search_cursor_date', None)
                    or datetime.fromisoformat(
                        (item.published_date or '1970') + '-01' * (3 - len((item.published_date or '1970').split('-')))
                    ),
                    snippet_text=(item.abstract_zh, item.abstract),
                )
                for item in papers
            )
        if include_materials:
            materials = await PipelineDao.list_search_materials(
                db,
                user_id,
                ranked=True,
                keyword=keyword,
                updated_from=date_from,
                updated_to=date_to,
                directions=direction_terms,
                offset=0,
                limit=candidate_limit,
                **({'search_after': search_after} if search_after is not None else {}),
            )
            rows.extend(
                cls._decorate_row(
                    cls._material_row(item, date_formatter),
                    keyword=keyword,
                    values=(item.name, item.edited_text if item.edited_text is not None else item.extracted_text),
                    cursor_date=getattr(item, '_search_cursor_date', item.updated_at),
                    sql_rank=getattr(item, '_search_rank', None),
                    snippet_text=(item.edited_text if item.edited_text is not None else item.extracted_text, None),
                )
                for item in materials
            )
        if include_reports:
            reports = await PipelineDao.list_search_reports(
                db,
                user_id,
                ranked=True,
                keyword=keyword,
                updated_from=date_from,
                updated_to=date_to,
                directions=direction_terms,
                offset=0,
                limit=candidate_limit,
                **({'search_after': search_after} if search_after is not None else {}),
            )
            rows.extend(
                cls._decorate_row(
                    cls._report_row(item, date_formatter),
                    keyword=keyword,
                    values=(item.title, item.content),
                    cursor_date=getattr(item, '_search_cursor_date', item.updated_at),
                    sql_rank=getattr(item, '_search_rank', None),
                    snippet_text=(None, getattr(item, 'content', None)),
                )
                for item in reports
            )
        if include_public:
            counts['news'] = await PipelineDao.count_articles(
                db,
                **article_filters,
                keyword=keyword,
                published_from=date_from,
                published_to=date_to,
                directions=direction_terms,
            )
            counts['paper'] = await PipelineDao.count_papers(
                db,
                keyword=keyword,
                published_from=date_from,
                published_to=date_to,
                directions=direction_terms,
            )
        if include_internal:
            counts['document'] = await PipelineDao.count_search_materials(
                db,
                user_id,
                keyword=keyword,
                updated_from=date_from,
                updated_to=date_to,
                directions=direction_terms,
            )
        if include_internal and content_type != 'evidence':
            counts['report'] = await PipelineDao.count_search_reports(
                db,
                user_id,
                keyword=keyword,
                updated_from=date_from,
                updated_to=date_to,
                directions=direction_terms,
            )

        total = (
            sum(counts.values())
            if content_type in {'all', 'evidence'}
            else counts['news' if content_type in {'website', 'wechat'} else content_type]
        )
        counts['all'] = sum(counts.values())

        for row in rows:
            row['title_parts'] = cls._highlight_parts(row.get('title'), keyword)
            summary, fallback = row.pop('_snippet_text', (row.get('summary'), None))
            row['summary_parts'] = cls._snippet_parts(summary, fallback, keyword)
        rows.sort(key=lambda row: cls._sort_key(row, keyword), reverse=True)
        start = 0 if search_after is not None else (page_num - 1) * page_size
        page_rows = rows[start : start + page_size]
        has_more = len(rows) > page_size if search_after is not None else total > start + len(page_rows)
        next_cursor = cls._encode_cursor(page_rows[-1], context=cursor_context) if has_more and page_rows else None
        for row in page_rows:
            row.pop('_search_rank', None)
            row.pop('_cursor_date', None)
        return {
            'rows': page_rows,
            'total': total,
            'counts': counts,
            'next_cursor': next_cursor,
        }
