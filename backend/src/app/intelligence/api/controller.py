"""Public content, category-prompt and template APIs."""

from typing import Annotated, Literal

from fastapi import HTTPException, Query, Request, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_ids import parse_business_id
from app.intelligence.schemas.pipeline import PipelineListModel, PipelineTemplateSaveModel
from app.intelligence.services.application import IntelligenceApplicationService
from app.intelligence.services.categories import CategoryService
from app.intelligence.services.templates import PipelineTemplateService
from app.system.api.dependencies import CurrentUserDependency, CurrentUserModel, PreAuthDependency
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import RoleInterfaceAuthDependency
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel

controller = APIRouterPro(prefix='/pipeline', order_num=30, tags=['管网情报'], dependencies=[PreAuthDependency()])
DB = Annotated[AsyncSession, DBSessionDependency()]
ADMIN = [RoleInterfaceAuthDependency('admin')]
BusinessId = Annotated[int, BeforeValidator(parse_business_id)]


@controller.get('/dashboard', dependencies=ADMIN)
async def dashboard(query_db: DB):
    return ResponseUtil.success(data=await IntelligenceApplicationService.dashboard_summary(query_db))


@controller.get('/portal/overview', summary='获取当前用户门户统计')
async def get_pipeline_portal_overview(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await IntelligenceApplicationService.portal_overview(query_db, user_id=current_user.user.user_id)
    return ResponseUtil.success(data=data)


catalog_tags_adapter = TypeAdapter(
    Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=20)]
)


@controller.get('/intelligence/list', summary='查询情报列表', response_model=DataResponseModel[PipelineListModel])
async def list_pipeline_intelligence(  # noqa: PLR0913
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    category: Annotated[str | None, Query(description='内容类别')] = None,
    keyword: Annotated[str | None, Query(description='关键词')] = None,
    source_type: Annotated[str | None, Query(description='来源类型')] = None,
    tag: Annotated[str | None, Query(alias='tag', max_length=100, description='标签；与分类、来源、等级取交集')] = None,
    tags: Annotated[str | None, Query(max_length=13000, description='新闻标签 JSON 数组，多个标签取交集')] = None,
    relevance_min: Annotated[int | None, Query(alias='relevanceMin', ge=0, le=100)] = None,
    relevance_max: Annotated[int | None, Query(alias='relevanceMax', ge=0, le=100)] = None,
    year_from: Annotated[int | None, Query(alias='yearFrom', ge=1600, le=2200)] = None,
    year_to: Annotated[int | None, Query(alias='yearTo', ge=1600, le=2200)] = None,
    access_status: Annotated[str | None, Query(alias='accessStatus', max_length=32)] = None,
    journal: Annotated[str | None, Query(max_length=255)] = None,
    sort_by: Annotated[Literal['publication'] | None, Query(alias='sortBy')] = None,
    page_num: Annotated[int, Query(alias='pageNum', ge=1)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=1, le=100)] = 10,
) -> Response:
    try:
        selected_tags = catalog_tags_adapter.validate_json(tags) if tags else []
    except ValidationError as error:
        raise HTTPException(status_code=422, detail='标签须为 JSON 数组，最多20项，每项1至100字') from error
    data = await IntelligenceApplicationService.list_intelligence(
        query_db,
        category=category,
        keyword=keyword,
        source_type=source_type,
        **({'tag': tag} if tag else {}),
        **({'tags': selected_tags} if selected_tags else {}),
        relevance_min=relevance_min,
        relevance_max=relevance_max,
        year_from=year_from,
        year_to=year_to,
        access_status=access_status,
        journal=journal,
        **({'sort_by': sort_by} if sort_by else {}),
        page_num=page_num,
        page_size=page_size,
    )
    return ResponseUtil.success(data=data)


@controller.get('/research/materials', summary='分页检索科研选材', response_model=DataResponseModel[PipelineListModel])
async def search_research_materials(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    content_type: Annotated[Literal['all', 'news', 'wechat', 'paper', 'document'], Query(alias='type')] = 'all',
    page_num: Annotated[int, Query(alias='pageNum', ge=1)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=10, le=50)] = 10,
) -> Response:
    if page_size not in {10, 20, 50}:
        raise HTTPException(status_code=422, detail='每页条数须为10、20或50')
    data = await IntelligenceApplicationService.search_intelligence(
        query_db,
        user_id=current_user.user.user_id,
        keyword=keyword,
        content_type={'all': 'evidence', 'news': 'website'}.get(content_type, content_type),
        source='internal'
        if content_type == 'document'
        else 'public'
        if content_type in {'news', 'wechat', 'paper'}
        else 'all',
        date_range='all',
        directions=None,
        page_num=page_num,
        page_size=page_size,
        max_page_num=None,
    )
    return ResponseUtil.success(data=data)


@controller.get('/intelligence/{item_id}', summary='获取情报详情')
async def get_pipeline_intelligence_detail(
    request: Request,
    item_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await IntelligenceApplicationService.get_intelligence_detail(query_db, item_id)
    return ResponseUtil.success(data=data)


@controller.get('/search', summary='统一检索情报和用户资料', response_model=DataResponseModel[PipelineListModel])
async def search_pipeline_intelligence(  # noqa: PLR0913
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    content_type: Annotated[str, Query(alias='type')] = 'all',
    source: Annotated[str, Query()] = 'all',
    date_range: Annotated[str, Query(alias='dateRange')] = 'all',
    directions: Annotated[str | None, Query(max_length=500)] = None,
    page_num: Annotated[int, Query(alias='pageNum', ge=1, le=100)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(alias='cursor', max_length=500)] = None,
) -> Response:
    data = await IntelligenceApplicationService.search_intelligence(
        query_db,
        user_id=current_user.user.user_id,
        keyword=keyword,
        content_type=content_type,
        source=source,
        date_range=date_range,
        directions=directions,
        page_num=page_num,
        page_size=page_size,
        cursor=cursor,
    )
    return ResponseUtil.success(data=data)


class CategorySave(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=100000)
    model_id: int | None = None
    applies_to: Literal['news', 'paper', 'all'] = 'all'
    is_enabled: bool = False
    sort_order: int = Field(default=0, ge=0)


@controller.get('/categories', dependencies=ADMIN)
async def list_categories(query_db: DB):
    return ResponseUtil.success(data=await CategoryService.list(query_db))


@controller.post('/categories', dependencies=ADMIN)
async def create_category(payload: CategorySave, query_db: DB):
    return ResponseUtil.success(data=await CategoryService.save(query_db, payload.model_dump()))


@controller.put('/categories/{identity}', dependencies=ADMIN)
async def update_category(identity: BusinessId, payload: CategorySave, query_db: DB):
    return ResponseUtil.success(data=await CategoryService.save(query_db, payload.model_dump(), identity))


@controller.delete('/categories/{identity}', dependencies=ADMIN)
async def delete_category(identity: BusinessId, query_db: DB):
    await CategoryService.remove(query_db, identity)
    return ResponseUtil.success(msg='类别已删除')


@controller.get('/templates/published')
async def published_templates(query_db: DB, category: str | None = None):
    return ResponseUtil.success(
        data=await PipelineTemplateService.list_templates(query_db, category=category, published_only=True)
    )


@controller.get('/templates', dependencies=ADMIN)
async def templates(query_db: DB, category: str | None = None):
    return ResponseUtil.success(data=await PipelineTemplateService.list_templates(query_db, category=category))


@controller.post('/templates', dependencies=ADMIN)
async def create_template(payload: PipelineTemplateSaveModel, query_db: DB):
    return ResponseUtil.success(
        data=await PipelineTemplateService.save_draft(
            query_db, template_key=None, payload=payload.model_dump(), operator_id=None, operator_name=''
        )
    )


@controller.put('/templates/{identity}', dependencies=ADMIN)
async def update_template(identity: BusinessId, payload: PipelineTemplateSaveModel, query_db: DB):
    return ResponseUtil.success(
        data=await PipelineTemplateService.save_draft(
            query_db, template_key=identity, payload=payload.model_dump(), operator_id=None, operator_name=''
        )
    )


@controller.delete('/templates/{identity}', dependencies=ADMIN)
async def disable_template(identity: BusinessId, query_db: DB):
    return ResponseUtil.success(data=await PipelineTemplateService.retire(query_db, identity))
