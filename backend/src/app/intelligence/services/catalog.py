"""Public news and paper-abstract read models; no review or handoff workflow."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.business_ids import parse_business_id, wire_id
from app.intelligence.repositories.content_repository import ContentDao
from exceptions.exception import ServiceException


class IntelligenceCatalogService:
    @staticmethod
    def article_dict(item: Any, *, detail: bool = False, date_formatter: Any) -> dict[str, Any]:
        source = item.source
        source_type = 'news' if source.type == 'website' else source.type
        category = item.category
        text = item.content_zh if item.content_zh is not None else item.content or ''
        data = {
            'id': wire_id(item.id),
            'category': source_type,
            'category_id': wire_id(item.category_id),
            'category_name': category.name if category else '',
            'title': item.title,
            'source': source.name,
            'source_type': source_type,
            'publish_time': date_formatter(item.published_at),
            'tags': [category.name] if category else [],
            'summary': text[:240],
            'source_url': item.url,
            'sourceUrl': item.url,
            'author': item.author or '',
            'is_pushed': item.is_pushed,
        }
        if detail:
            data.update(content=text, content_original=item.content or '', content_zh=item.content_zh)
        return data

    @staticmethod
    def paper_dict(item: Any, *, detail: bool = False, date_formatter: Any) -> dict[str, Any]:
        category = item.category
        abstract = item.abstract_zh if item.abstract_zh is not None else item.abstract or ''
        date = item.published_date or ''
        source = item.source.name if item.source else item.journal or '论文数据库'
        data = {
            'id': wire_id(item.id),
            'category': 'paper',
            'category_id': wire_id(item.category_id),
            'category_name': category.name if category else '',
            'title': item.title,
            'title_zh': item.title_zh,
            'source': source,
            'source_type': 'paper',
            'publish_time': date,
            'publication_year': int(date[:4]) if date else None,
            'tags': [category.name] if category else [],
            'summary': abstract,
            'source_url': item.url or '',
            'sourceUrl': item.url or '',
            'doi': item.doi or '',
            'authors': [name.strip() for name in (item.authors or '').split(';') if name.strip()],
            'journal': item.journal or '',
            'is_pushed': item.is_pushed,
        }
        if detail:
            data.update(content=abstract, abstract=item.abstract, abstract_zh=item.abstract_zh)
        return data

    @staticmethod
    async def portal_overview(db: Any, *, user_id: int, now: datetime | None = None) -> dict[str, Any]:
        shanghai = ZoneInfo('Asia/Shanghai')
        current = now.astimezone(shanghai) if now else datetime.now(shanghai)
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        counts = await ContentDao.portal_overview_counts(
            db, user_id=user_id, start=start, end=start + timedelta(days=1)
        )
        return {
            'paperCount': counts['paper_count'],
            'newsCount': counts['news_count'],
            'wechatCount': counts['wechat_count'],
            'todayPaperCount': counts['today_paper_count'],
            'todayNewsCount': counts['today_news_count'],
            'todayWechatCount': counts['today_wechat_count'],
            'todayAddedCount': counts['today_added_count'],
            'reportCount': counts['report_count'],
            'todayDate': current.date().isoformat(),
        }

    @classmethod
    async def list_intelligence(
        cls,
        db: Any,
        *,
        category: str | None,
        keyword: str | None,
        source_type: str | None,
        page_num: int,
        page_size: int,
        date_formatter: Any,
        **filters: Any,
    ) -> dict[str, Any]:
        if page_num < 1 or not 1 <= page_size <= 100:
            raise ServiceException(message='分页参数不正确')
        article_type = (
            source_type if source_type in {'news', 'wechat'} else category if category in {'news', 'wechat'} else None
        )
        category_id = category if category not in {None, 'news', 'wechat', 'paper', 'article'} else None
        query = dict(filters, keyword=keyword, category_id=category_id, offset=0, limit=page_num * page_size)
        rows = []
        total = 0
        if category != 'paper' and source_type != 'paper':
            articles = await ContentDao.list_articles(db, article_type=article_type, **query)
            rows.extend(cls.article_dict(item, date_formatter=date_formatter) for item in articles)
            total += await ContentDao.count_articles(db, article_type=article_type, **query)
        if category not in {'news', 'wechat', 'article'} and source_type not in {'news', 'wechat'}:
            papers = await ContentDao.list_papers(db, **query)
            rows.extend(cls.paper_dict(item, date_formatter=date_formatter) for item in papers)
            total += await ContentDao.count_papers(db, **query)
        rows.sort(key=lambda row: (row['publish_time'], parse_business_id(row['id'])), reverse=True)
        offset = (page_num - 1) * page_size
        return {'rows': rows[offset : offset + page_size], 'total': total}

    @classmethod
    async def get_detail(cls, db: Any, item_id: str, *, date_formatter: Any) -> dict[str, Any]:
        item_id = parse_business_id(item_id)
        article = await ContentDao.get_article(db, item_id)
        if article:
            return cls.article_dict(article, detail=True, date_formatter=date_formatter)
        paper = await ContentDao.get_paper(db, item_id)
        if paper:
            return cls.paper_dict(paper, detail=True, date_formatter=date_formatter)
        raise ServiceException(message='情报资料不存在')
