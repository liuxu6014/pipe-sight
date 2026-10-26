"""Portal application service without retired review, routing or handoff flows."""

from app.business_time import format_business_time
from app.intelligence.services.catalog import IntelligenceCatalogService
from app.intelligence.services.dashboard import IntelligenceDashboardService
from app.intelligence.services.search import IntelligenceSearchService


class IntelligenceApplicationService:
    @staticmethod
    def _datetime_text(value):
        return format_business_time(value)

    @classmethod
    async def dashboard_summary(cls, db):
        return await IntelligenceDashboardService.summary(db, date_formatter=cls._datetime_text)

    @staticmethod
    async def portal_overview(db, *, user_id):
        return await IntelligenceCatalogService.portal_overview(db, user_id=user_id)

    @classmethod
    async def list_intelligence(cls, db, **kwargs):
        return await IntelligenceCatalogService.list_intelligence(db, **kwargs, date_formatter=cls._datetime_text)

    @classmethod
    async def get_intelligence_detail(cls, db, item_id):
        return await IntelligenceCatalogService.get_detail(db, item_id, date_formatter=cls._datetime_text)

    @classmethod
    async def search_intelligence(cls, db, **kwargs):
        return await IntelligenceSearchService.search(db, **kwargs, date_formatter=cls._datetime_text)
