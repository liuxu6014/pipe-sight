"""资料篮仅持有来源外键；列表重新授权并解析实时标题。"""

from sqlalchemy.exc import IntegrityError

from app.business_ids import parse_business_id, wire_id
from app.library.repositories.material_repository import MaterialDao
from app.research.models.research_models import PipelineWorkspaceItem
from app.research.repositories.research_repository import ResearchDao
from exceptions.exception import ServiceException


class ResearchWorkspaceService:
    targets = {
        'article': 'article_id',
        'paper': 'paper_id',
        'file': 'file_id',
        'material': 'file_id',
        'report': 'report_id',
    }

    @classmethod
    async def _source(cls, db, user_id, kind, item_id):
        if kind in {'file', 'material'}:
            return await MaterialDao.get_owned_material(db, item_id, user_id)
        if kind == 'report':
            return await ResearchDao.get_report(db, item_id, user_id)
        if kind in {'article', 'paper'}:
            return await ResearchDao.load_content(db, kind, item_id)
        raise ServiceException(message='资料篮类型不合法')

    @classmethod
    async def list_items(cls, db, user_id):
        rows = await ResearchDao.list_workspace_items(db, user_id)
        favorite, basket = [], []
        for row in rows:
            kind = next(
                key for key in ('article', 'paper', 'file', 'report') if getattr(row, cls.targets[key]) is not None
            )
            item_id = getattr(row, cls.targets[kind])
            source = await cls._source(db, user_id, kind, item_id)
            if not source:
                continue
            item = {'id': wire_id(item_id), 'type': kind, 'title': source.name if kind == 'file' else source.title}
            (favorite if row.action == 'favorite' else basket).append(item)
        return {'favorites': [i['id'] for i in favorite], 'favoriteItems': favorite, 'basket': basket}

    @classmethod
    async def upsert_item(cls, db, user_id, payload):
        item_id = parse_business_id(payload.item_id)
        if payload.action not in {'basket', 'favorite'} or payload.item_type not in cls.targets:
            raise ServiceException(message='资料篮操作或来源不合法')
        source = await cls._source(db, user_id, payload.item_type, payload.item_id)
        if not source:
            raise ServiceException(message='资料不存在或无权访问')
        existing = await ResearchDao.get_workspace_item(db, user_id, payload.item_type, payload.item_id, payload.action)
        if not existing:
            row = PipelineWorkspaceItem(
                user_id=user_id, action=payload.action, **{cls.targets[payload.item_type]: item_id}
            )
            try:
                await ResearchDao.add_workspace_item(db, row)
                await db.commit()
            except IntegrityError:
                await db.rollback()
                if not await ResearchDao.get_workspace_item(
                    db, user_id, payload.item_type, payload.item_id, payload.action
                ):
                    raise
        return {'itemId': wire_id(item_id), 'action': payload.action, 'saved': True}

    @staticmethod
    async def delete_item(db, user_id, item_id, action):
        await ResearchDao.delete_workspace_item(db, user_id, item_id, action)
        await db.commit()
        return {'itemId': wire_id(item_id), 'action': action, 'deleted': True}
