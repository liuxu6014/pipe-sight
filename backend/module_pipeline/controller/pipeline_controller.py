from typing import Annotated

from fastapi import BackgroundTasks, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from config.env import UploadConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.common_service import CommonService
from module_pipeline.entity.vo.pipeline_vo import (
    PipelineDashboardModel,
    PipelineDiagramUpdateModel,
    PipelineKnowledgeAnswerModel,
    PipelineKnowledgeAskModel,
    PipelineListModel,
    PipelineReportExportModel,
    PipelineReportUpdateModel,
    PipelineResearchJobCreateModel,
    PipelineTaskModel,
    PipelineWorkspaceItemMutationModel,
)
from module_pipeline.service.pipeline_domain_service import PipelineDomainService
from module_pipeline.service.pipeline_service import PipelineService
from utils.response_util import ResponseUtil

pipeline_controller = APIRouterPro(
    prefix='/pipeline',
    order_num=30,
    tags=['管网情报'],
    dependencies=[PreAuthDependency()],
)


@pipeline_controller.get(
    '/dashboard', summary='获取管网情报工作台', response_model=DataResponseModel[PipelineDashboardModel]
)
async def get_pipeline_dashboard(request: Request) -> Response:
    return ResponseUtil.success(data=PipelineService.get_dashboard_summary())


@pipeline_controller.get(
    '/intelligence/list', summary='查询情报列表', response_model=DataResponseModel[PipelineListModel]
)
async def list_pipeline_intelligence(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    category: Annotated[str | None, Query(description='内容类别')] = None,
    keyword: Annotated[str | None, Query(description='关键词')] = None,
    source_type: Annotated[str | None, Query(description='来源类型')] = None,
    page_num: Annotated[int, Query(alias='pageNum', ge=1)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=1, le=100)] = 10,
) -> Response:
    data = await PipelineDomainService.list_intelligence(
        query_db,
        category=category,
        keyword=keyword,
        source_type=source_type,
        page_num=page_num,
        page_size=page_size,
    )
    return ResponseUtil.success(data=data)


@pipeline_controller.get('/intelligence/{item_id}', summary='获取情报详情')
async def get_pipeline_intelligence_detail(
    request: Request,
    item_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineDomainService.get_intelligence_detail(query_db, item_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.get('/sources', summary='查询数据源列表', response_model=DataResponseModel[PipelineListModel])
async def list_pipeline_sources(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.list_sources(query_db))


@pipeline_controller.get('/tasks', summary='查询采集任务列表', response_model=DataResponseModel[PipelineListModel])
async def list_pipeline_tasks(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.list_collection_tasks(query_db))


@pipeline_controller.post(
    '/tasks/{task_id}/run', summary='手动运行采集任务', response_model=DataResponseModel[PipelineTaskModel]
)
async def run_pipeline_task(
    request: Request,
    task_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.queue_collection_run(query_db, task_id))


@pipeline_controller.post('/tasks/runs/{run_id}/handoff', summary='提交采集结果到外部处理系统')
async def dispatch_pipeline_handoff(
    request: Request,
    run_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineDomainService.dispatch_insighthub_handoff(query_db, run_id)
    return ResponseUtil.success(data=data, msg='采集结果已提交处理')


@pipeline_controller.post('/tasks/runs/{run_id}/handoff/sync', summary='同步外部处理结果')
async def sync_pipeline_handoff(
    request: Request,
    run_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineDomainService.sync_insighthub_handoff(query_db, run_id)
    return ResponseUtil.success(data=data, msg='外部处理结果已同步')


@pipeline_controller.get('/reports', summary='查询报告草稿列表', response_model=DataResponseModel[PipelineListModel])
async def list_pipeline_reports(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_reports(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.get(
    '/reports/{report_id}/export',
    summary='导出报告Markdown',
    response_model=DataResponseModel[PipelineReportExportModel],
)
async def export_pipeline_report(
    request: Request,
    report_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    report = await PipelineDomainService.get_report(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data={'fileName': f'{report["title"]}.md', 'content': report['content']})


@pipeline_controller.get(
    '/knowledge/documents',
    summary='查询知识库文档',
    response_model=DataResponseModel[PipelineListModel],
)
async def list_pipeline_knowledge_documents(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_materials(
        query_db,
        current_user.user.user_id,
    )
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/knowledge/documents', summary='上传知识库资料')
async def upload_pipeline_knowledge_document(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    file: Annotated[UploadFile, File(...)],
    category: Annotated[str, Form()] = '内部文献',
    permission_scope: Annotated[str, Form(alias='permissionScope')] = 'private',
    tags: Annotated[str, Form()] = '',
) -> Response:
    upload_result = await CommonService.upload_service(request, file)
    stored = upload_result.result
    owner_name = current_user.user.nick_name or current_user.user.user_name
    local_path = (
        stored.file_name.replace(UploadConfig.UPLOAD_PREFIX, UploadConfig.UPLOAD_PATH)
        if stored and stored.file_name
        else None
    )
    data = await PipelineDomainService.create_material(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=owner_name,
        name=stored.original_filename or file.filename or '未命名资料',
        category=category,
        permission_scope=permission_scope,
        file_name=stored.new_file_name,
        file_path=stored.file_name,
        file_url=stored.url,
        mime_type=file.content_type,
        file_size=file.size or 0,
        local_path=local_path,
        tags=[item.strip() for item in tags.split(',') if item.strip()],
    )
    return ResponseUtil.success(data=data, msg='资料上传成功')


@pipeline_controller.get('/knowledge/documents/{material_id}', summary='获取知识库资料详情')
async def get_pipeline_knowledge_document(
    request: Request,
    material_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.get_material(
        query_db,
        current_user.user.user_id,
        material_id,
    )
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/knowledge/documents/{material_id}/retry', summary='重新解析知识库资料')
async def retry_pipeline_knowledge_document(
    request: Request,
    material_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.retry_material_parse(
        query_db,
        current_user.user.user_id,
        material_id,
    )
    return ResponseUtil.success(data=data, msg='资料解析状态已更新')


@pipeline_controller.delete('/knowledge/documents/{material_id}', summary='删除知识库资料')
async def delete_pipeline_knowledge_document(
    request: Request,
    material_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.delete_material(
        query_db,
        current_user.user.user_id,
        material_id,
    )
    return ResponseUtil.success(data=data, msg='资料已删除')


@pipeline_controller.post(
    '/knowledge/ask',
    summary='知识库问答',
    response_model=DataResponseModel[PipelineKnowledgeAnswerModel],
)
async def ask_pipeline_knowledge(
    request: Request,
    body: PipelineKnowledgeAskModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.ask_knowledge(
        query_db,
        user_id=current_user.user.user_id,
        question=body.question,
        document_ids=body.document_ids,
        document_types=body.document_types,
    )
    return ResponseUtil.success(data=data)


@pipeline_controller.get('/workspace', summary='获取用户资料篮与收藏')
async def get_pipeline_workspace(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_workspace(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/workspace/items', summary='保存用户资料篮或收藏条目')
async def save_pipeline_workspace_item(
    request: Request,
    body: PipelineWorkspaceItemMutationModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.upsert_workspace_item(query_db, current_user.user.user_id, body)
    return ResponseUtil.success(data=data, msg='工作区状态已保存')


@pipeline_controller.delete('/workspace/items/{action}/{item_id}', summary='移除用户资料篮或收藏条目')
async def delete_pipeline_workspace_item(
    request: Request,
    action: str,
    item_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    if action not in {'favorite', 'basket'}:
        return ResponseUtil.failure(msg='不支持的工作区动作')
    data = await PipelineDomainService.delete_workspace_item(
        query_db,
        current_user.user.user_id,
        item_id,
        action,
    )
    return ResponseUtil.success(data=data, msg='工作区条目已移除')


@pipeline_controller.get('/research/jobs', summary='查询当前用户科研生成任务')
async def list_pipeline_research_jobs(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_research_jobs(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/research/jobs', summary='创建科研报告或日报周月报任务')
async def create_pipeline_research_job(
    request: Request,
    background_tasks: BackgroundTasks,
    body: PipelineResearchJobCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.queue_research_job(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        payload=body,
    )
    background_tasks.add_task(
        PipelineDomainService.process_queued_research_job,
        job_id=data['jobId'],
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='任务已进入后台生成队列')


@pipeline_controller.get('/research/jobs/{job_id}', summary='获取科研生成任务进度')
async def get_pipeline_research_job(
    request: Request,
    job_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.get_research_job(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/research/jobs/{job_id}/cancel', summary='取消科研生成任务')
async def cancel_pipeline_research_job(
    request: Request,
    job_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.cancel_research_job(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data, msg='任务已取消')


@pipeline_controller.post('/research/jobs/{job_id}/retry', summary='按原配置重新生成科研任务')
async def retry_pipeline_research_job(
    request: Request,
    background_tasks: BackgroundTasks,
    job_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.queue_research_job_retry(
        query_db,
        user_id=current_user.user.user_id,
        job_id=job_id,
    )
    background_tasks.add_task(
        PipelineDomainService.process_queued_research_job,
        job_id=data['jobId'],
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='任务已重新进入后台生成队列')


@pipeline_controller.get('/research/reports', summary='查询当前用户科研报告与日报周月报')
async def list_pipeline_research_reports(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_reports(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.get('/research/reports/{report_id}', summary='获取科研报告详情')
async def get_pipeline_research_report(
    request: Request,
    report_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.get_report(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.put('/research/reports/{report_id}', summary='自动保存或发布科研报告')
async def update_pipeline_research_report(
    request: Request,
    report_id: str,
    body: PipelineReportUpdateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.update_report(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        report_id=report_id,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='报告已保存')


@pipeline_controller.get('/research/reports/{report_id}/diagram', summary='获取科研报告结构化图形')
async def get_pipeline_research_report_diagram(
    request: Request,
    report_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.get_report_diagram(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.put('/research/reports/{report_id}/diagram', summary='保存科研报告结构化图形')
async def update_pipeline_research_report_diagram(
    request: Request,
    report_id: str,
    body: PipelineDiagramUpdateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.update_report_diagram(
        query_db,
        user_id=current_user.user.user_id,
        report_id=report_id,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='图形已保存')


@pipeline_controller.get('/research/reports/{report_id}/versions', summary='查询科研报告版本')
async def list_pipeline_research_report_versions(
    request: Request,
    report_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.list_report_versions(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data=data)


@pipeline_controller.get('/research/reports/{report_id}/versions/{version_no}', summary='获取科研报告历史版本')
async def get_pipeline_research_report_version(
    request: Request,
    report_id: str,
    version_no: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.get_report_version(
        query_db,
        current_user.user.user_id,
        report_id,
        version_no,
    )
    return ResponseUtil.success(data=data)


@pipeline_controller.post('/research/reports/{report_id}/versions/{version_no}/restore', summary='恢复科研报告历史版本')
async def restore_pipeline_research_report_version(
    request: Request,
    report_id: str,
    version_no: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.restore_report_version(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        report_id=report_id,
        version_no=version_no,
    )
    return ResponseUtil.success(data=data, msg='历史版本已恢复并保存为新版本')


@pipeline_controller.get('/research/reports/{report_id}/export', summary='导出科研报告Markdown')
async def export_pipeline_research_report(
    request: Request,
    report_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    report = await PipelineDomainService.get_report(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data={'fileName': f'{report["title"]}.md', 'content': report['content']})
