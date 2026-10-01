from typing import Annotated
from urllib.parse import quote

from fastapi import BackgroundTasks, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from config.env import UploadConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.common_service import CommonService
from module_pipeline.entity.vo.pipeline_vo import (
    PipelineDashboardModel,
    PipelineDiagramUpdateModel,
    PipelineListModel,
    PipelinePromptModel,
    PipelinePromptSaveModel,
    PipelineReportExportModel,
    PipelineReportUpdateModel,
    PipelineResearchJobCreateModel,
    PipelineSourceSaveModel,
    PipelineTaskModel,
    PipelineTemplateModel,
    PipelineTemplateSaveModel,
    PipelineWorkspaceItemMutationModel,
)
from module_pipeline.service.pipeline_domain_service import PipelineDomainService
from module_pipeline.service.pipeline_prompt_service import PipelinePromptService
from module_pipeline.service.pipeline_template_service import PipelineTemplateService
from utils.response_util import ResponseUtil
from utils.upload_util import UploadUtil

pipeline_controller = APIRouterPro(
    prefix='/pipeline',
    order_num=30,
    tags=['管网情报'],
    dependencies=[PreAuthDependency()],
)


@pipeline_controller.get(
    '/dashboard', summary='获取管网情报工作台', response_model=DataResponseModel[PipelineDashboardModel]
)
async def get_pipeline_dashboard(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.get_dashboard_summary(query_db))


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


@pipeline_controller.get(
    '/sources',
    summary='查询数据源列表',
    response_model=DataResponseModel[PipelineListModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:source:list')],
)
async def list_pipeline_sources(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.list_sources(query_db))


@pipeline_controller.post(
    '/sources',
    summary='新增数据源',
    dependencies=[UserInterfaceAuthDependency('pipeline:source:save')],
)
async def create_pipeline_source(
    request: Request,
    payload: PipelineSourceSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.save_source(
        query_db,
        source_id=None,
        source_code=payload.source_code,
        name=payload.name,
        source_type=payload.source_type,
        endpoint=payload.endpoint,
        adapter_key=payload.adapter_key,
        schedule_cron=payload.schedule_cron,
        enabled=payload.enabled,
        config_json=payload.config_json,
        handoff_mode=payload.handoff_mode,
        processor_source_code=payload.processor_source_code,
        owner_id=current_user.user.user_id,
    )
    return ResponseUtil.success(data=data, msg='数据源已创建')


@pipeline_controller.put(
    '/sources/{source_id}',
    summary='更新数据源',
    dependencies=[UserInterfaceAuthDependency('pipeline:source:save')],
)
async def update_pipeline_source(
    request: Request,
    source_id: str,
    payload: PipelineSourceSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineDomainService.save_source(
        query_db,
        source_id=source_id,
        source_code=payload.source_code,
        name=payload.name,
        source_type=payload.source_type,
        endpoint=payload.endpoint,
        adapter_key=payload.adapter_key,
        schedule_cron=payload.schedule_cron,
        enabled=payload.enabled,
        config_json=payload.config_json,
        handoff_mode=payload.handoff_mode,
        processor_source_code=payload.processor_source_code,
        owner_id=current_user.user.user_id,
    )
    return ResponseUtil.success(data=data, msg='数据源已更新')


@pipeline_controller.delete(
    '/sources/{source_id}',
    summary='停用数据源',
    dependencies=[UserInterfaceAuthDependency('pipeline:source:save')],
)
async def disable_pipeline_source(
    request: Request,
    source_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineDomainService.set_source_enabled(query_db, source_id, False)
    return ResponseUtil.success(data=data, msg='数据源已停用')


@pipeline_controller.get(
    '/templates',
    summary='查询模板版本',
    response_model=DataResponseModel[PipelineListModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:template:list')],
)
async def list_pipeline_templates(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    category: Annotated[str | None, Query(description='模板分类')] = None,
    published_only: Annotated[bool, Query(alias='publishedOnly')] = False,
) -> Response:
    return ResponseUtil.success(
        data=await PipelineTemplateService.list_templates(query_db, category=category, published_only=published_only)
    )


@pipeline_controller.post(
    '/templates',
    summary='新增模板草稿',
    response_model=DataResponseModel[PipelineTemplateModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:template:save')],
)
async def create_pipeline_template(
    request: Request,
    payload: PipelineTemplateSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineTemplateService.save_draft(
        query_db,
        template_key=payload.template_key,
        payload=payload.model_dump(by_alias=False),
        operator_id=current_user.user.user_id,
        operator_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='模板草稿已保存')


@pipeline_controller.put(
    '/templates/{template_key}',
    summary='保存模板新版本',
    response_model=DataResponseModel[PipelineTemplateModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:template:save')],
)
async def update_pipeline_template(
    request: Request,
    template_key: str,
    payload: PipelineTemplateSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineTemplateService.save_draft(
        query_db,
        template_key=template_key,
        payload=payload.model_dump(by_alias=False),
        operator_id=current_user.user.user_id,
        operator_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='模板新版本已保存为草稿')


@pipeline_controller.post(
    '/templates/{template_key}/publish',
    summary='发布模板版本',
    response_model=DataResponseModel[PipelineTemplateModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:template:publish')],
)
async def publish_pipeline_template(
    request: Request,
    template_key: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelineTemplateService.publish(
        query_db,
        template_key,
        operator_id=current_user.user.user_id,
        operator_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='模板已发布')


@pipeline_controller.delete(
    '/templates/{template_key}',
    summary='停用模板',
    response_model=DataResponseModel[PipelineTemplateModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:template:publish')],
)
async def retire_pipeline_template(
    request: Request,
    template_key: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineTemplateService.retire(query_db, template_key)
    return ResponseUtil.success(data=data, msg='模板已停用')


@pipeline_controller.get(
    '/prompts',
    summary='查询提示词版本',
    response_model=DataResponseModel[PipelineListModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:prompt:list')],
)
async def list_pipeline_prompts(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    scene: Annotated[str | None, Query(description='业务场景')] = None,
) -> Response:
    data = await PipelinePromptService.list_prompts(query_db, scene=scene)
    return ResponseUtil.success(data=data)


@pipeline_controller.post(
    '/prompts',
    summary='保存提示词草稿',
    response_model=DataResponseModel[PipelinePromptModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:prompt:save')],
)
async def save_pipeline_prompt(
    request: Request,
    payload: PipelinePromptSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelinePromptService.save_draft(
        query_db,
        prompt_key=payload.prompt_key,
        scene=payload.scene,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        operator_id=current_user.user.user_id,
        operator_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='提示词草稿已保存')


@pipeline_controller.post(
    '/prompts/{prompt_key}/test',
    summary='离线测试提示词结构',
    response_model=DataResponseModel[PipelinePromptModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:prompt:test')],
)
async def test_pipeline_prompt(
    request: Request,
    prompt_key: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelinePromptService.test_prompt(query_db, prompt_key)
    return ResponseUtil.success(data=data, msg='提示词离线结构测试通过')


@pipeline_controller.post(
    '/prompts/{prompt_key}/publish',
    summary='发布提示词版本',
    response_model=DataResponseModel[PipelinePromptModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:prompt:publish')],
)
async def publish_pipeline_prompt(
    request: Request,
    prompt_key: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await PipelinePromptService.publish_prompt(
        query_db,
        prompt_key,
        operator_id=current_user.user.user_id,
        operator_name=current_user.user.nick_name or current_user.user.user_name,
    )
    return ResponseUtil.success(data=data, msg='提示词已发布，后续采集将使用该版本')


@pipeline_controller.get(
    '/tasks',
    summary='查询采集任务列表',
    response_model=DataResponseModel[PipelineListModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:task:list')],
)
async def list_pipeline_tasks(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.list_collection_tasks(query_db))


@pipeline_controller.post(
    '/tasks/{task_id}/run',
    summary='手动运行采集任务',
    response_model=DataResponseModel[PipelineTaskModel],
    dependencies=[UserInterfaceAuthDependency('pipeline:task:run')],
)
async def run_pipeline_task(
    request: Request,
    task_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PipelineDomainService.queue_collection_run(query_db, task_id))


@pipeline_controller.post(
    '/tasks/runs/{run_id}/handoff',
    summary='提交采集结果到外部处理系统',
    dependencies=[UserInterfaceAuthDependency('pipeline:task:run')],
)
async def dispatch_pipeline_handoff(
    request: Request,
    run_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PipelineDomainService.dispatch_insighthub_handoff(query_db, run_id)
    return ResponseUtil.success(data=data, msg='采集结果已提交处理')


@pipeline_controller.post(
    '/tasks/runs/{run_id}/handoff/sync',
    summary='同步外部处理结果',
    dependencies=[UserInterfaceAuthDependency('pipeline:task:run')],
)
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


@pipeline_controller.get(
    '/knowledge/documents/{material_id}/download',
    summary='受控下载知识库资料',
    response_class=StreamingResponse,
)
async def download_pipeline_knowledge_document(
    request: Request,
    material_id: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    file_path, file_name, media_type = await PipelineDomainService.get_material_download(
        query_db,
        current_user.user.user_id,
        material_id,
    )
    return ResponseUtil.streaming(
        data=UploadUtil.generate_file(str(file_path)),
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(file_name)}"},
        media_type=media_type or 'application/octet-stream',
    )


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
