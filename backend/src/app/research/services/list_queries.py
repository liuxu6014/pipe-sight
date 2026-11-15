"""Bounded list read models. Article bodies and frozen prompts stay in detail APIs."""

from sqlalchemy import case, func, or_, select

from app.business_ids import wire_id
from app.business_time import format_business_time
from app.library.models.materials import PipelineMaterial as Material
from app.research.models.research_models import PipelineReport as Report
from app.research.models.research_models import PipelineReportVersion as Version
from app.research.models.research_models import PipelineResearchJob as Job
from app.system.models.user import SysUser


async def report_page(
    db, *, user_id=None, page=1, page_size=20, keyword='', status='', kind='', sort='updated-desc', start='', end=''
) -> dict:
    latest = select(
        Job.report_id,
        Job.id.label('job_id'),
        Job.status.label('job_status'),
        Job.progress,
        func.row_number().over(partition_by=Job.report_id, order_by=(Job.created_at.desc(), Job.id.desc())).label('rn'),
    ).subquery()
    has_output = func.length(func.trim(Report.content)) > 0
    state = case(
        (has_output, 'generated'),
        (latest.c.job_status.in_(['queued', 'running']), 'active'),
        (latest.c.job_status == 'failed', 'failed'),
        (latest.c.job_status == 'cancelled', 'cancelled'),
        else_='unavailable',
    )
    period = Version.model_snapshot['request']['period']
    query = (
        select(
            Report.id,
            Report.user_id,
            Report.title,
            Report.type,
            Report.version,
            Report.created_at,
            Report.updated_at,
            has_output.label('has_output'),
            func.length(Report.content).label('words'),
            state.label('list_status'),
            latest.c.job_id,
            latest.c.job_status,
            latest.c.progress,
            SysUser.nickname.label('owner'),
            period.label('period'),
        )
        .outerjoin(latest, (latest.c.report_id == Report.id) & (latest.c.rn == 1))
        .outerjoin(Version, (Version.report_id == Report.id) & (Version.version == Report.version))
        .outerjoin(SysUser, SysUser.id == Report.user_id)
    )
    if user_id is not None:
        query = query.where(Report.user_id == user_id)
    digest_types = ['daily', 'weekly', 'monthly']
    if kind in digest_types:
        query = query.where(Report.type == kind)
    elif kind == 'digest':
        query = query.where(Report.type.in_(digest_types))
    elif kind == 'brief':
        query = query.where(Report.type.in_(['weekly', 'monthly']))
    elif kind == 'research':
        query = query.where(Report.type.not_in(digest_types))
    if keyword.strip():
        term = '%' + keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.where(or_(Report.title.ilike(term, escape='\\'), SysUser.nickname.ilike(term, escape='\\')))
    normalized_status = {
        'completed': 'generated',
        'draft': 'unavailable',
        '已完成': 'generated',
        '已生成': 'generated',
        '生成失败': 'failed',
        '生成中': 'active',
        '排队中': 'active',
        '已取消': 'cancelled',
    }.get(status, status)
    if normalized_status in {'queued', 'running'}:
        # Administrator filters distinguish queueing from execution, while the
        # personal workspace also offers their combined "active" group.
        query = query.where(~has_output, latest.c.job_status == normalized_status)
    elif normalized_status and normalized_status != 'all':
        query = query.where(state == normalized_status)
    # ISO dates in snapshot periods retain lexical order. Missing periods never match.
    if start:
        query = query.where(func.coalesce(period[1].as_string(), period[0].as_string()) >= start)
    if end:
        query = query.where(period[0].as_string() <= end)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    order = {
        'updated-asc': Report.updated_at.asc(),
        'title': Report.title.asc(),
        'title-desc': Report.title.desc(),
    }.get(sort, Report.updated_at.desc())
    rows = (
        (await db.execute(query.order_by(order, Report.id.desc()).offset((page - 1) * page_size).limit(page_size)))
        .mappings()
        .all()
    )
    return {
        'rows': [
            {
                'id': wire_id(r['id']),
                'reportId': wire_id(r['id']),
                'ownerId': r['user_id'],
                'owner': r['owner'],
                'title': r['title'],
                'type': r['type'],
                'reportType': r['type'],
                'hasOutput': bool(r['has_output']),
                'status': 'completed' if r['has_output'] else (r['job_status'] or 'draft'),
                'listStatus': r['list_status'],
                'version': f'V{r["version"]}.0',
                'versionNo': r['version'],
                'words': r['words'],
                'jobId': wire_id(r['job_id']),
                'progress': r['progress'] or 0,
                'period': r['period'] or '',
                'metadata': {'period': r['period'] or ''},
                'updatedAt': format_business_time(r['updated_at']),
                'createdAt': format_business_time(r['created_at']),
            }
            for r in rows
        ],
        'total': total or 0,
        'pageNum': page,
        'pageSize': page_size,
    }


async def material_page(db, *, user_id, page=1, page_size=20, keyword='', status='', classification='') -> dict:
    query = select(
        Material.id,
        Material.user_id,
        Material.name,
        Material.filename,
        Material.size,
        Material.hash,
        Material.status,
        Material.error,
        Material.version,
        Material.updated_at,
        Material.created_at,
        func.substr(func.coalesce(Material.edited_text, Material.extracted_text, ''), 1, 240).label('summary'),
    ).where(Material.user_id == user_id)
    if keyword.strip():
        term = '%' + keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.where(
            or_(
                Material.name.ilike(term, escape='\\'),
                func.coalesce(Material.edited_text, Material.extracted_text, '').ilike(term, escape='\\'),
            )
        )
    groups = {'已解析': ['ready'], '处理中': ['queued', 'parsing'], '异常': ['failed']}
    if status and status != 'all':
        query = query.where(Material.status.in_(groups.get(status, [status])))
    if classification:
        # Materials currently have no classification field; never invent one from file type.
        query = query.where(False)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await db.execute(
                query.order_by(Material.updated_at.desc(), Material.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        'rows': [
            {
                'id': wire_id(r['id']),
                'ownerId': r['user_id'],
                'canManage': True,
                'name': r['name'],
                'fileName': r['filename'],
                'fileSize': r['size'],
                'fileHash': r['hash'],
                'format': r['filename'].rsplit('.', 1)[-1].upper(),
                'type': '内部文献',
                'permissionScope': 'private',
                'permission': '仅自己可见',
                'parseStatus': r['status'],
                'status': {'ready': '已解析', 'queued': '等待解析', 'parsing': '解析中', 'failed': '解析失败'}.get(
                    r['status'], r['status']
                ),
                'parseMessage': r['error'] or '',
                'summary': r['summary'],
                'versionNo': r['version'],
                'version': f'V{r["version"]}.0',
                'updatedAt': format_business_time(r['updated_at']),
                'createdAt': format_business_time(r['created_at']),
            }
            for r in rows
        ],
        'total': total or 0,
        'pageNum': page,
        'pageSize': page_size,
    }


async def job_page(db, *, user_id, page=1, page_size=20, keyword='', status='') -> dict:
    # Extract only two display scalars from JSON. Never select the frozen
    # prompt/material snapshot, generated manuscript or history for a list.
    title = func.coalesce(Job.config_snapshot['title'].as_string(), Report.title)
    report_type = func.coalesce(Job.config_snapshot['type'].as_string(), Report.type)
    has_output = func.length(func.trim(Report.content)) > 0
    query = (
        select(
            Job.id,
            Job.report_id,
            Job.status,
            Job.progress,
            Job.created_at,
            Job.updated_at,
            Job.started_at,
            Job.finished_at,
            Report.user_id,
            title.label('title'),
            report_type.label('type'),
            has_output.label('has_output'),
        )
        .join(Report, Report.id == Job.report_id)
        .where(Report.user_id == user_id)
    )
    if keyword.strip():
        query = query.where(title.contains(keyword.strip(), autoescape=True))
    if status == 'active':
        query = query.where(Job.status.in_(['queued', 'running']))
    elif status and status != 'all':
        query = query.where(Job.status == status)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await db.execute(
                query.order_by(Job.created_at.desc(), Job.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    labels = {
        'queued': '等待生成',
        'running': '生成中',
        'completed': '已完成',
        'failed': '生成失败',
        'cancelled': '已取消',
    }
    return {
        'rows': [
            {
                'id': wire_id(row['id']),
                'jobId': wire_id(row['id']),
                'reportId': wire_id(row['report_id']),
                'ownerId': row['user_id'],
                'title': row['title'],
                'type': row['type'],
                'reportType': row['type'],
                'status': row['status'],
                'statusLabel': labels[row['status']],
                'stage': row['status'],
                'progress': row['progress'],
                'reportStatus': 'completed' if row['has_output'] else 'draft',
                'requiresReview': False,
                'createdAt': format_business_time(row['created_at']),
                'updatedAt': format_business_time(row['updated_at']),
                'startedAt': format_business_time(row['started_at']),
                'finishedAt': format_business_time(row['finished_at']),
            }
            for row in rows
        ],
        'total': total or 0,
        'pageNum': page,
        'pageSize': page_size,
    }
