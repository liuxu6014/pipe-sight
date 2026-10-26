"""在提交事务内加载、授权并冻结真实资料，不依赖审核或旧分类表。"""

from copy import deepcopy

from app.business_ids import parse_business_id, wire_id
from app.library.repositories.material_repository import MaterialDao
from app.research.repositories.research_repository import ResearchDao
from exceptions.exception import ServiceException


class ResearchEvidenceService:
    @staticmethod
    def effective_text(item):
        return item.edited_text if item.edited_text is not None else (item.extracted_text or '')

    @classmethod
    async def resolve(cls, db, user_id, selected_ids, payload=None, **_):
        if not selected_ids or len(selected_ids) > 50:
            raise ServiceException(message='请选择 1 至 50 条资料，超限不会截断')
        result, seen = [], set()
        for selection in selected_ids:
            # 新协议建议 {type,id}；旧 ID 可适配，但同 ID 跨表歧义明确拒绝。
            if isinstance(selection, dict):
                kind, item_id = selection.get('type'), selection.get('id')
                kinds = [kind]
            else:
                item_id = selection
                kinds = ['file', 'article', 'paper']
            item_id = parse_business_id(item_id)
            matches = []
            for kind in kinds:
                if kind == 'file':
                    item = await MaterialDao.get_owned_material(db, item_id, user_id)
                    if item:
                        content = cls.effective_text(item)
                        if item.status != 'ready' or not content.strip():
                            raise ServiceException(message='所选资料尚未解析就绪或有效正文为空')
                        matches.append(
                            {
                                'type': 'file',
                                'id': wire_id(item.id),
                                'title': item.name,
                                'content': content,
                                'source': {'filename': item.filename},
                            }
                        )
                elif kind in {'article', 'paper'}:
                    item = await ResearchDao.load_content(db, kind, item_id)
                    if item is None:
                        continue
                    if kind == 'paper':
                        content = item.abstract_zh or item.abstract or ''
                        source = {
                            'doi': item.doi,
                            'url': item.url,
                            'journal': item.journal,
                            'authors': item.authors,
                            'published_date': item.published_date,
                        }
                        title = item.title_zh or item.title
                    else:
                        content = item.content_zh or item.content or ''
                        source = {
                            'url': item.url,
                            'source_id': wire_id(item.source_id),
                            'published_at': item.published_at.isoformat() if item.published_at else None,
                        }
                        title = item.title
                    if not content.strip():
                        raise ServiceException(message='所选内容没有可用正文或论文摘要')
                    matches.append(
                        {'type': kind, 'id': wire_id(item.id), 'title': title, 'content': content, 'source': source}
                    )
                else:
                    raise ServiceException(message='选材类型只能为 article、paper、file')
            if len(matches) != 1:
                raise ServiceException(message='所选资料失效、无权访问或 ID 存在类型歧义，请重新选材')
            item = matches[0]
            key = (item['type'], item['id'])
            if key in seen:
                raise ServiceException(message='同一类型和 ID 不可重复选材')
            seen.add(key)
            result.append(item)
        return deepcopy(result)
