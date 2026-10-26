"""独立采集管理 API，主代理负责装配此 router 及移除旧路由。"""

from typing import Annotated

from fastapi import HTTPException, Request
from pydantic import BeforeValidator
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_ids import parse_business_id
from app.intelligence.repositories.collection_repository import CollectionConflict
from app.intelligence.schemas.collection import CollectionRequest, IsolationConfirmation, SourceEnabled, SourceSave
from app.intelligence.services.collection import ConfigurationError
from app.intelligence.services.sources import IntelligenceSourceService as Sources
from app.system.api.dependencies import PreAuthDependency
from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import RoleInterfaceAuthDependency, UserInterfaceAuthDependency
from common.enums.audit import BusinessType
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro

collection_controller = APIRouterPro(
    prefix='/pipeline',
    auto_register=False,
    tags=['采集管理'],
    dependencies=[PreAuthDependency(), RoleInterfaceAuthDependency('admin')],
)
DB = Annotated[AsyncSession, DBSessionDependency()]
BusinessId = Annotated[int, BeforeValidator(parse_business_id)]


async def response(operation):
    try:
        return ResponseUtil.success(data=await operation)
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CollectionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@collection_controller.get('/sources', dependencies=[UserInterfaceAuthDependency('pipeline:source:list')])
async def list_sources(request: Request, query_db: DB):
    return await response(Sources.list_sources(query_db))


@collection_controller.post('/sources', dependencies=[UserInterfaceAuthDependency('pipeline:source:save')])
@Log(title='采集来源', business_type=BusinessType.INSERT, request_log_mode='summary', response_log_mode='summary')
async def create_source(request: Request, payload: SourceSave, query_db: DB):
    return await response(Sources.save(query_db, **payload.model_dump()))


@collection_controller.put('/sources/{source_id}', dependencies=[UserInterfaceAuthDependency('pipeline:source:save')])
@Log(title='采集来源', business_type=BusinessType.UPDATE, request_log_mode='summary', response_log_mode='summary')
async def save_source(request: Request, source_id: BusinessId, payload: SourceSave, query_db: DB):
    return await response(Sources.save(query_db, source_id=source_id, **payload.model_dump()))


@collection_controller.put(
    '/sources/{source_id}/enabled', dependencies=[UserInterfaceAuthDependency('pipeline:source:save')]
)
@Log(title='采集启停', business_type=BusinessType.UPDATE, request_log_mode='summary', response_log_mode='summary')
async def set_enabled(request: Request, source_id: BusinessId, payload: SourceEnabled, query_db: DB):
    return await response(Sources.set_enabled(query_db, source_id, payload.is_enabled))


@collection_controller.post('/tasks/{source_id}/run', dependencies=[UserInterfaceAuthDependency('pipeline:task:run')])
@Log(title='采集入队', business_type=BusinessType.INSERT, request_log_mode='summary', response_log_mode='summary')
async def enqueue(request: Request, source_id: BusinessId, query_db: DB, payload: CollectionRequest | None = None):
    return await response(
        Sources.queue_collection_run(query_db, source_id, request_id=payload.request_id if payload else None)
    )


@collection_controller.get('/tasks', dependencies=[UserInterfaceAuthDependency('pipeline:task:list')])
async def list_runs(request: Request, query_db: DB):
    return await response(Sources.list_collection_tasks(query_db))


@collection_controller.get('/tasks/runs/{run_id}', dependencies=[UserInterfaceAuthDependency('pipeline:task:list')])
async def detail(request: Request, run_id: BusinessId, query_db: DB):
    return await response(Sources.get_collection_run_detail(query_db, run_id))


@collection_controller.post(
    '/tasks/runs/{run_id}/stop', dependencies=[UserInterfaceAuthDependency('pipeline:task:run')]
)
@Log(title='采集停止', business_type=BusinessType.UPDATE, request_log_mode='summary', response_log_mode='summary')
async def stop(request: Request, run_id: BusinessId, query_db: DB):
    return await response(Sources.stop_collection_run(query_db, run_id))


@collection_controller.post(
    '/tasks/runs/{run_id}/retry', dependencies=[UserInterfaceAuthDependency('pipeline:task:run')]
)
@Log(title='采集重试', business_type=BusinessType.INSERT, request_log_mode='summary', response_log_mode='summary')
async def retry(request: Request, run_id: BusinessId, query_db: DB, payload: CollectionRequest | None = None):
    return await response(
        Sources.retry_collection_run(query_db, run_id, request_id=payload.request_id if payload else None)
    )


@collection_controller.post(
    '/tasks/runs/{run_id}/confirm-stop', dependencies=[UserInterfaceAuthDependency('pipeline:task:run')]
)
@Log(
    title='确认采集进程已隔离',
    business_type=BusinessType.UPDATE,
    request_log_mode='summary',
    response_log_mode='summary',
)
async def confirm_stop(request: Request, run_id: BusinessId, payload: IsolationConfirmation, query_db: DB):
    return await response(Sources.confirm_isolated_stop(query_db, run_id, worker_isolated=payload.worker_isolated))


@collection_controller.delete(
    '/sources/{source_id}', dependencies=[UserInterfaceAuthDependency('pipeline:source:save')]
)
@Log(title='采集停用', business_type=BusinessType.UPDATE, request_log_mode='summary', response_log_mode='summary')
async def disable_source(request: Request, source_id: BusinessId, query_db: DB):
    return await response(Sources.set_enabled(query_db, source_id, False))
