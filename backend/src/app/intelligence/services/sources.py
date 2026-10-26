"""采集来源管理。仅依赖采集专属仓储；终态记录和冻结快照不可重写。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.intelligence.models.collection import PipelineCrawlRun as Run
from app.intelligence.models.collection import PipelineSource as Source
from app.intelligence.repositories.collection_repository import CollectionConflict, CollectionRepository, aware
from app.intelligence.services.collection import ADAPTERS, ConfigurationError
from app.intelligence.services.collection_translation import CollectionTranslationService, TranslationConfigurationError

UTC = timezone.utc
RETRYABLE_ERRORS = {
    '临时采集故障或请求超时',
    '存在未成功处理的候选条目',
    '执行器租约过期',
    '执行器中断',
    '候选条目分类失败，请检查后台类别模型后重试',
    '候选条目自动翻译失败，请检查模型后重试',
}


def transaction(method):
    @wraps(method)
    async def wrapped(*args, **kwargs):
        db = args[1]
        try:
            return await method(*args, **kwargs)
        except BaseException:
            await db.rollback()
            raise

    return wrapped


def next_occurrence(cron, tz, after):
    """UTC cursor; CronTrigger chooses DST occurrences, skip missed history.

    Nonexistent wall times are skipped. On a repeated wall time the two UTC
    occurrences are distinct schedule slots and have distinct idempotency keys.
    """
    try:
        zone = ZoneInfo(tz)
        if not cron:
            return None
        if len(cron) > 100 or len(cron.split()) != 5:
            raise ValueError('cron 必须为五字段')
        trigger = CronTrigger.from_crontab(cron, timezone=zone)
        candidate = trigger.get_next_fire_time(None, after + timedelta(microseconds=1))
        # APScheduler may return a nominal nonexistent wall time: reject it by
        # round-tripping through UTC and move to the following occurrence.
        for _ in range(10):
            if candidate is None:
                raise ValueError('表达式无后续执行时间')
            utc = candidate.astimezone(timezone.utc)
            if utc.astimezone(zone).replace(fold=0) == candidate.replace(fold=0):
                return utc
            candidate = trigger.get_next_fire_time(candidate, utc + timedelta(seconds=1))
        raise ValueError('时区时间无有效执行点')
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        raise ConfigurationError('无效 cron 或 IANA 时区') from exc


def snapshot(source):
    return deepcopy(
        {
            'source': {'id': wire_id(source.id)},
            **{key: getattr(source, key) for key in ('adapter', 'url', 'type', 'config', 'model_id')},
        }
    )


async def frozen_snapshot(db, source):
    try:
        return await CollectionTranslationService.freeze(db, snapshot(source))
    except TranslationConfigurationError as exc:
        raise ConfigurationError(str(exc)) from None


def run_dict(run):
    # Execution tokens and credential references aren't public API output.
    keys = (
        'id',
        'source_id',
        'parent_id',
        'trigger_type',
        'request_id',
        'status',
        'available_at',
        'checkpoint',
        'fetched_count',
        'saved_count',
        'failed_count',
        'error',
        'stop_requested_at',
        'started_at',
        'finished_at',
        'created_at',
        'updated_at',
    )
    result = {
        key: (format_business_time(value) if key in {'created_at', 'updated_at'}
              else aware(value).isoformat() if isinstance(value, datetime) else value)
        for key in keys
        for value in [getattr(run, key)]
    }
    for key in ('id', 'source_id', 'parent_id'):
        result[key] = wire_id(result[key])
    for key, value in list(result.items()):
        first, *rest = key.split('_')
        result[first + ''.join(part.title() for part in rest)] = value
    result['runId'] = wire_id(run.id)
    return result


class IntelligenceSourceService:
    @staticmethod
    def source_dict(source, date_formatter=None):
        data = {col.name: getattr(source, col.name) for col in Source.__table__.columns}
        data['id'] = wire_id(source.id)
        for key in ('created_at', 'updated_at'):
            data[key] = format_business_time(data[key])
        for key in ('next_run_at',):
            value = data[key]
            data[key] = (date_formatter(value) if date_formatter else value.isoformat()) if value else None
        for key, value in list(data.items()):
            first, *rest = key.split('_')
            data[first + ''.join(part.title() for part in rest)] = value
        data.update(sourceId=wire_id(source.id), sourceCode=wire_id(source.id), source_code=wire_id(source.id))
        return data

    @classmethod
    @transaction
    async def save(
        cls,
        db,
        *,
        source_id=None,
        name,
        type,
        url=None,
        adapter,
        cron=None,
        timezone='Asia/Shanghai',
        config=None,
        model_id=None,
        is_enabled=True,
        registry=ADAPTERS,
        clock=None,
        date_formatter=None,
    ):
        source_id = parse_business_id(source_id) if source_id is not None else None
        now = (clock or (lambda: datetime.now(UTC)))()
        if not isinstance(name, str) or not name.strip() or len(name) > 255:
            raise ConfigurationError('来源名称无效')
        if not isinstance(is_enabled, bool):
            raise ConfigurationError('is_enabled 必须为布尔值')
        cron = (cron or '').strip() or None
        next_time = next_occurrence(cron, timezone, now)  # Validate even disabled sources.
        effective = {
            'adapter': adapter,
            'url': url,
            'type': type,
            'config': config if config is not None else {},
            'model_id': model_id,
        }
        registry.validate(effective)
        source = (
            await CollectionRepository.source(db, source_id, lock=True)
            if source_id is not None
            else Source(created_at=now)
        )
        if source_id and source.type != type:
            # No cross-domain content relabelling through a source edit.
            raise CollectionConflict('来源 type 创建后不可修改，请新建来源')
        for key, value in effective.items():
            setattr(source, key, deepcopy(value))
        source.name, source.cron, source.timezone = name.strip(), cron, timezone
        source.is_enabled, source.next_run_at, source.updated_at = is_enabled, next_time if is_enabled else None, now
        db.add(source)
        await db.flush()
        if not is_enabled:
            run = await CollectionRepository.active(db, source.id)
            if run and run.status == 'queued':
                run.stop_requested_at = now
                CollectionRepository.terminal(run, 'cancelled', now)
        await db.commit()
        return cls.source_dict(source, date_formatter)

    @classmethod
    @transaction
    async def set_enabled(cls, db, source_id, enabled, *, date_formatter=None, registry=ADAPTERS, clock=None):
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        if not isinstance(enabled, bool):
            raise ConfigurationError('启停值必须为布尔值')
        source = await CollectionRepository.source(db, source_id, lock=True)
        if enabled:
            registry.validate(snapshot(source))
        cursor = next_occurrence(source.cron, source.timezone, now) if enabled else None
        source = await CollectionRepository.set_enabled(db, source_id, enabled, now=now, next_run_at=cursor)
        return cls.source_dict(source, date_formatter)

    @classmethod
    @transaction
    async def queue_collection_run(cls, db, source_id, *, request_id=None, registry=ADAPTERS, clock=None):
        source_id = parse_business_id(source_id)
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        source = await CollectionRepository.source(db, source_id, lock=True)
        if request_id:
            previous = (await db.execute(select(Run).where(Run.request_id == request_id))).scalars().first()
            if previous:
                if previous.source_id != source_id or previous.trigger_type != 'manual':
                    raise CollectionConflict('request_id 已被其他请求使用')
                await db.commit()
                return run_dict(previous)
        active = await CollectionRepository.active(db, source_id)
        if active:
            await db.commit()
            return run_dict(active)
        config = await frozen_snapshot(db, source)
        registry.validate(config)
        run = await CollectionRepository.enqueue(
            db, source_id, request_id=request_id or f'manual:{uuid4()}', now=now, snapshot=config
        )
        return run_dict(run)

    @classmethod
    @transaction
    async def stop_collection_run(cls, db, run_id, *, clock=None):
        run = await CollectionRepository.stop(db, run_id, now=(clock or (lambda: datetime.now(timezone.utc)))())
        result = run_dict(run)
        result['message'] = '已请求停止' if run.status == 'stopping' else run.status
        return result

    @classmethod
    @transaction
    async def confirm_isolated_stop(cls, db, run_id, *, worker_isolated, clock=None):
        if worker_isolated is not True:
            raise CollectionConflict('须确认工作进程/外部请求已经隔离并退出')
        _, run = await CollectionRepository.locked_run(db, run_id)
        if run.status not in ('stopping', 'cancelled'):
            raise CollectionConflict('仅确认正在停止的运行，不修改其他终态')
        run = await CollectionRepository.recover(
            db, run_id, now=(clock or (lambda: datetime.now(UTC)))(), isolated=True
        )
        return run_dict(run)

    @classmethod
    @transaction
    async def retry_collection_run(cls, db, run_id, *, automatic=False, request_id=None, registry=ADAPTERS, clock=None):
        run_id = parse_business_id(run_id)
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        source, parent = await CollectionRepository.locked_run(db, run_id)
        child = (await db.execute(select(Run).where(Run.parent_id == run_id))).scalars().first()
        if child:
            await db.commit()
            return run_dict(child)
        eligible = parent.status == 'failed' and source.is_enabled and parent.stop_requested_at is None
        retryable = parent.error in RETRYABLE_ERRORS
        if not eligible or not retryable:
            if automatic:
                await db.commit()
                return None
            raise CollectionConflict('仅可重试启用来源的可恢复 failed 运行；配置错误须修复后新建手动运行')
        adapter = registry.validate(parent.config_snapshot)
        retry = parent.config_snapshot['config'].get('retry', {})
        depth, cursor, visited = 0, parent, set()
        while True:
            if cursor.id in visited or cursor.source_id != source.id:
                raise CollectionConflict('重试链无效')
            visited.add(cursor.id)
            if not cursor.parent_id:
                break
            cursor = await CollectionRepository.run(db, cursor.parent_id)
            depth += 1
        if automatic and (not retry.get('enabled', False) or depth >= retry.get('max_retries', 0)):
            await db.commit()
            return None
        delay = min(retry.get('backoff_seconds', 30) * 2 ** min(depth, 20), retry.get('max_backoff_seconds', 3600))
        run = await CollectionRepository.enqueue(
            db,
            source.id,
            request_id=request_id or f'retry:{run_id}',
            now=now,
            available_at=now + timedelta(seconds=delay),
            trigger_type='retry',
            parent_id=run_id,
            snapshot=parent.config_snapshot,
            checkpoint=parent.checkpoint if adapter.supports_resume else {},
        )
        return run_dict(run)

    @classmethod
    @transaction
    async def schedule_due_source(cls, db, source_id, *, registry=ADAPTERS, clock=None):
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        source = await CollectionRepository.source(db, source_id, lock=True)
        if not source.is_enabled or not source.cron or not source.next_run_at or aware(source.next_run_at) > now:
            await db.commit()
            return None
        due = aware(source.next_run_at).astimezone(timezone.utc)
        registry.validate(snapshot(source))
        source.next_run_at, source.updated_at = next_occurrence(source.cron, source.timezone, now), now
        await db.flush()
        if await CollectionRepository.active(db, source_id):
            import logging

            logging.getLogger(__name__).info('采集本轮跳过，来源仍有活跃运行: %s', source_id)
            await db.commit()
            return None
        run = await CollectionRepository.enqueue(
            db,
            source_id,
            now=now,
            snapshot=await frozen_snapshot(db, source),
            request_id=f'schedule:{source_id}:{due.isoformat()}',
            trigger_type='schedule',
        )
        return run_dict(run)

    @classmethod
    async def list_sources(cls, db, *, date_formatter=None):
        rows = list((await db.execute(select(Source).order_by(Source.created_at.desc(), Source.id))).scalars().all())
        return {
            'rows': [cls.source_dict(row, date_formatter) for row in rows],
            'total': len(rows),
            'message': '' if rows else '尚未配置采集来源，请先新增来源并选择已注册的采集适配器',
        }

    @staticmethod
    async def get_collection_run_detail(db, run_id):
        run = await CollectionRepository.run(db, run_id)
        source = await CollectionRepository.source(db, run.source_id)
        return {
            **run_dict(run),
            'sourceId': wire_id(source.id),
            'sourceName': source.name,
            'isEnabled': source.is_enabled,
            'canRetry': run.status == 'failed'
            and source.is_enabled
            and run.error in RETRYABLE_ERRORS
            and run.stop_requested_at is None,
        }

    @staticmethod
    async def list_collection_tasks(db):
        rows = []
        for source, latest in await CollectionRepository.source_tasks(db):
            rows.append(
                {
                    'id': wire_id(source.id),
                    'sourceId': wire_id(source.id),
                    'source': source.name,
                    'name': f'{source.name}采集',
                    'source_code': wire_id(source.id),
                    'sourceCode': wire_id(source.id),
                    'isEnabled': source.is_enabled,
                    'latestRunId': wire_id(latest.id) if latest else None,
                    'status': latest.status if latest else 'waiting',
                    'nextRunAt': aware(source.next_run_at).isoformat() if source.next_run_at else None,
                    'latestMessage': latest.error
                    if latest and latest.error
                    else ('尚未执行采集' if latest is None else f'最近运行状态：{latest.status}'),
                    'fetchedCount': latest.fetched_count if latest else 0,
                    'savedCount': latest.saved_count if latest else 0,
                    'failedCount': latest.failed_count if latest else 0,
                }
            )
        return {
            'rows': rows,
            'total': len(rows),
            'message': '' if rows else '尚未配置采集来源，请先在来源管理中新增来源',
        }
