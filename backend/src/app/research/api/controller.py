"""资料篮、科研任务和报告成果 API。"""

from typing import Annotated
from urllib.parse import quote

from fastapi import Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_ids import wire_id
from app.intelligence.schemas.pipeline import (
    BusinessId,
    PipelineDiagramUpdateModel,
    PipelineDigestCandidatesModel,
    PipelineDigestScheduleCreateModel,
    PipelineDigestScheduleToggleModel,
    PipelineReportExportCreateModel,
    PipelineReportUpdateModel,
    PipelineResearchJobCreateModel,
    PipelineWorkspaceItemMutationModel,
)
from app.research.digest_policy import DIGEST_SELECTION_LIMIT
from app.research.repositories.research_repository import ResearchDao as PipelineDao
from app.research.schemas.generation import ApplyGenerationResultModel
from app.research.services.application import ResearchApplicationService
from app.research.services.exports import ResearchReportExportService
from app.research.services.reports import ResearchReportService
from app.system.api.dependencies import CurrentUserDependency, CurrentUserModel, PreAuthDependency
from common.aspect.db_seesion import DBSessionDependency
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro

controller = APIRouterPro(
    prefix='/pipeline',
    order_num=30,
    tags=['管网情报'],
    dependencies=[PreAuthDependency()],
)


@controller.get('/research/assets/{asset_id}/download', summary='下载本人图片或导出资源')
async def download_research_asset(
    asset_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    name, mime, content = await ResearchReportExportService.download(
        query_db, user_id=current_user.user.user_id, export_id=asset_id
    )
    return Response(
        content=content, media_type=mime, headers={'Content-Disposition': f"inline; filename*=UTF-8''{quote(name)}"}
    )


@controller.post('/research/assets/{asset_id}/retry', summary='独立重试失败图片或导出资源')
async def retry_research_asset(
    asset_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    return ResponseUtil.success(
        data=await ResearchReportExportService.retry(query_db, current_user.user.user_id, asset_id)
    )


@controller.post('/research/digest-candidates', summary='筛选并去重简报候选资料')
async def search_digest_candidates(
    body: PipelineDigestCandidatesModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    rows, total = await PipelineDao.search_digest_candidates(query_db, body)
    return ResponseUtil.success(
        data={
            'rows': [{'id': wire_id(row.id), 'title': row.title} for row in rows],
            'total': total,
            'selectionLimit': DIGEST_SELECTION_LIMIT,
        }
    )


@controller.post('/research/jobs/{job_id}/apply-result', summary='显式应用生成结果并保存历史版本')
async def apply_generation_result(
    job_id: BusinessId,
    body: ApplyGenerationResultModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchReportService.apply_task_result(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        job_id=job_id,
        expected_version=body.expected_version,
        report_serializer=ResearchApplicationService.report_dict,
    )
    return ResponseUtil.success(data=data)


@controller.get('/workspace', summary='获取用户资料篮与收藏')
async def get_pipeline_workspace(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_workspace(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@controller.post('/workspace/items', summary='保存用户资料篮或收藏条目')
async def save_pipeline_workspace_item(
    request: Request,
    body: PipelineWorkspaceItemMutationModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.upsert_workspace_item(query_db, current_user.user.user_id, body)
    return ResponseUtil.success(data=data, msg='工作区状态已保存')


@controller.delete('/workspace/items/{action}/{item_id}', summary='移除用户资料篮或收藏条目')
async def delete_pipeline_workspace_item(
    request: Request,
    action: str,
    item_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    if action not in {'favorite', 'basket'}:
        return ResponseUtil.failure(msg='不支持的工作区动作')
    data = await ResearchApplicationService.delete_workspace_item(
        query_db,
        current_user.user.user_id,
        item_id,
        action,
    )
    return ResponseUtil.success(data=data, msg='工作区条目已移除')


@controller.get('/research/jobs', summary='查询当前用户科研生成任务')
async def list_pipeline_research_jobs(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_jobs(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@controller.post('/research/jobs', summary='创建科研报告或日报周月报任务')
async def create_pipeline_research_job(
    request: Request,
    body: PipelineResearchJobCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.queue_job(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='任务已进入后台生成队列')


@controller.get('/research/jobs/{job_id}', summary='获取科研生成任务进度')
async def get_pipeline_research_job(
    request: Request,
    job_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.get_job(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data)


@controller.post('/research/jobs/{job_id}/cancel', summary='取消科研生成任务')
async def cancel_pipeline_research_job(
    request: Request,
    job_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.cancel_job(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data, msg='任务已取消')


@controller.post('/research/jobs/{job_id}/retry', summary='按原配置重新生成科研任务')
async def retry_pipeline_research_job(
    request: Request,
    job_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.queue_retry(
        query_db,
        user_id=current_user.user.user_id,
        job_id=job_id,
    )
    return ResponseUtil.success(data=data, msg='任务已重新进入后台生成队列')


@controller.get('/research/digest-schedules', summary='查询当前用户周期简报自动计划')
async def list_pipeline_digest_schedules(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_digest_schedules(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@controller.post('/research/digest-schedules', summary='创建周期简报自动计划')
async def create_pipeline_digest_schedule(
    request: Request,
    body: PipelineDigestScheduleCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.create_digest_schedule(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='自动计划已保存，Worker将在下次执行时间派发任务')


@controller.put('/research/digest-schedules/{schedule_id}', summary='启用或停用周期简报自动计划')
async def toggle_pipeline_digest_schedule(
    request: Request,
    schedule_id: BusinessId,
    body: PipelineDigestScheduleToggleModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.set_digest_schedule_enabled(
        query_db,
        current_user.user.user_id,
        schedule_id,
        body.enabled,
    )
    return ResponseUtil.success(data=data, msg='自动计划状态已更新')


@controller.post('/research/digest-schedules/{schedule_id}/run', summary='立即补跑周期简报自动计划')
async def run_pipeline_digest_schedule_now(
    request: Request,
    schedule_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.run_digest_schedule_now(
        query_db,
        current_user.user.user_id,
        schedule_id,
    )
    return ResponseUtil.success(data=data, msg='自动计划已进入补跑队列，Worker将在短时间内派发任务')


@controller.delete('/research/digest-schedules/{schedule_id}', summary='删除周期简报自动计划')
async def delete_pipeline_digest_schedule(
    request: Request,
    schedule_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    await ResearchApplicationService.delete_digest_schedule(query_db, current_user.user.user_id, schedule_id)
    return ResponseUtil.success(msg='自动计划已删除')


@controller.get('/research/reports', summary='查询当前用户科研报告与日报周月报')
async def list_pipeline_research_reports(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_reports(
        query_db,
        current_user.user.user_id,
    )
    return ResponseUtil.success(data=data)


@controller.get('/research/reports/{report_id}', summary='获取科研报告详情')
async def get_pipeline_research_report(
    request: Request,
    report_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.get_report(
        query_db,
        current_user.user.user_id,
        report_id,
        include_all=bool(current_user.user.admin),
    )
    return ResponseUtil.success(data=data)


@controller.put('/research/reports/{report_id}', summary='自动保存或发布科研报告')
async def update_pipeline_research_report(
    request: Request,
    report_id: BusinessId,
    body: PipelineReportUpdateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.update_report(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        report_id=report_id,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='报告已保存')


@controller.get('/research/reports/{report_id}/diagram', summary='获取科研报告结构化图形')
async def get_pipeline_research_report_diagram(
    request: Request,
    report_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.get_report_diagram(query_db, current_user.user.user_id, report_id)
    return ResponseUtil.success(data=data)


@controller.put('/research/reports/{report_id}/diagram', summary='保存科研报告结构化图形')
async def update_pipeline_research_report_diagram(
    request: Request,
    report_id: BusinessId,
    body: PipelineDiagramUpdateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.update_report_diagram(
        query_db,
        user_id=current_user.user.user_id,
        report_id=report_id,
        payload=body,
    )
    return ResponseUtil.success(data=data, msg='图形已保存')


@controller.get('/research/reports/{report_id}/versions', summary='查询科研报告版本')
async def list_pipeline_research_report_versions(
    request: Request,
    report_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_report_versions(query_db, current_user.user.user_id, report_id, include_all=bool(current_user.user.admin))
    return ResponseUtil.success(data=data)


@controller.get('/research/reports/{report_id}/versions/{version_no}', summary='获取科研报告历史版本')
async def get_pipeline_research_report_version(
    request: Request,
    report_id: BusinessId,
    version_no: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.get_report_version(
        query_db,
        current_user.user.user_id,
        report_id,
        version_no,
        include_all=bool(current_user.user.admin),
    )
    return ResponseUtil.success(data=data)


@controller.post('/research/reports/{report_id}/versions/{version_no}/restore', summary='恢复科研报告历史版本')
async def restore_pipeline_research_report_version(
    request: Request,
    report_id: BusinessId,
    version_no: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.restore_report_version(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=current_user.user.nick_name or current_user.user.user_name,
        report_id=report_id,
        version_no=version_no,
    )
    return ResponseUtil.success(data=data, msg='历史版本已恢复并保存为新版本')


@controller.get('/research/reports/{report_id}/export', summary='导出科研报告')
async def export_pipeline_research_report(
    request: Request,
    report_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    allow_draft: bool = Query(default=False, alias='allowDraft', description='是否允许导出待复核草稿'),
    file_format: Annotated[str, Query(alias='format', description='markdown、docx 或 pdf')] = 'markdown',
) -> Response:
    if file_format.strip().lower() in {'docx', 'pdf'}:
        file_name, media_type, content = await ResearchApplicationService.export_report_file(
            query_db,
            current_user.user.user_id,
            report_id,
            file_format,
            allow_draft=allow_draft,
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(file_name)}"},
        )
    data = await ResearchApplicationService.export_report(
        query_db,
        current_user.user.user_id,
        report_id,
        allow_draft=allow_draft,
    )
    return ResponseUtil.success(data=data)


@controller.post('/research/reports/{report_id}/exports', summary='创建科研报告导出任务')
async def create_pipeline_research_report_export(
    request: Request,
    report_id: BusinessId,
    body: PipelineReportExportCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.create_report_export(
        query_db,
        current_user.user.user_id,
        report_id,
        body.export_format,
        allow_draft=body.allow_draft,
    )
    return ResponseUtil.success(data=data, msg='导出任务已创建')


@controller.get('/research/reports/{report_id}/exports', summary='查询科研报告导出记录')
async def list_pipeline_research_report_exports(
    request: Request,
    report_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ResearchApplicationService.list_report_exports(query_db, current_user.user.user_id, report_id, include_all=bool(current_user.user.admin))
    return ResponseUtil.success(data=data)


@controller.get('/research/exports/{export_id}/download', summary='下载科研报告导出文件')
async def download_pipeline_research_report_export(
    request: Request,
    export_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    file_name, media_type, content = await ResearchApplicationService.download_report_export(
        query_db,
        current_user.user.user_id,
        export_id,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )
