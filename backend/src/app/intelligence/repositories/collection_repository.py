"""采集专属事务仓储。所有状态写入按 source → run 顺序加锁。

使用独立、expire_on_commit=False 的 Session；每个公开写操作提交或回滚。
网络 I/O 不得在这些事务内发生。共享 PipelineDao 不参与采集执行。
"""

from copy import deepcopy
from datetime import timedelta, timezone
from functools import wraps
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.business_ids import parse_business_id
from app.intelligence.models.collection import PipelineCrawlRun as Run
from app.intelligence.models.collection import PipelineSource as Source

ACTIVE = ('queued', 'running', 'stopping')
TERMINAL = ('success', 'failed', 'cancelled')


def write_operation(method):
    @wraps(method)
    async def wrapped(cls, db, *args, **kwargs):
        try:
            return await method(cls, db, *args, **kwargs)
        except BaseException:
            await db.rollback()
            raise

    return wrapped


class CollectionConflict(ValueError):
    pass


class LeaseLost(CollectionConflict):
    pass


def aware(value):
    # Only used by the in-memory SQLite tests (SQLite drops timezone offsets).
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class CollectionRepository:
    @staticmethod
    async def source(db, source_id, *, lock=False):
        source_id = parse_business_id(source_id)
        stmt = select(Source).where(Source.id == source_id).execution_options(populate_existing=True)
        if lock:
            stmt = stmt.with_for_update()
        source = (await db.execute(stmt)).scalars().first()
        if source is None:
            raise CollectionConflict('数据源不存在')
        return source

    @staticmethod
    async def run(db, run_id):
        run_id = parse_business_id(run_id)
        run = (
            (await db.execute(select(Run).where(Run.id == run_id).execution_options(populate_existing=True)))
            .scalars()
            .first()
        )
        if run is None:
            raise CollectionConflict('采集运行不存在')
        return run

    @classmethod
    async def locked_run(cls, db, run_id):
        run_id = parse_business_id(run_id)
        # The source ID is immutable after insertion.
        source_id = (await db.execute(select(Run.source_id).where(Run.id == run_id))).scalar_one_or_none()
        if source_id is None:
            raise CollectionConflict('采集运行不存在')
        source = await cls.source(db, source_id, lock=True)
        run = (
            (
                await db.execute(
                    select(Run).where(Run.id == run_id).with_for_update().execution_options(populate_existing=True)
                )
            )
            .scalars()
            .one()
        )
        return source, run

    @staticmethod
    async def active(db, source_id):
        source_id = parse_business_id(source_id)
        return (
            (await db.execute(select(Run).where(Run.source_id == source_id, Run.status.in_(ACTIVE)))).scalars().first()
        )

    @staticmethod
    def terminal(run, status, now, error=None):
        run.status = status
        run.error = error
        run.finished_at = now
        run.updated_at = now
        run.execution_token = None
        run.lease_expires_at = None

    @staticmethod
    def fence(run, token, now, *, allow_stopping=False):
        states = ('running', 'stopping') if allow_stopping else ('running',)
        if (
            run.status not in states
            or not token
            or run.execution_token != token
            or run.lease_expires_at is None
            or aware(run.lease_expires_at) <= now
        ):
            raise LeaseLost('执行令牌或租约失效，禁止提交')

    @classmethod
    @write_operation
    async def enqueue(
        cls,
        db,
        source_id,
        *,
        request_id,
        now,
        snapshot,
        trigger_type='manual',
        parent_id=None,
        available_at=None,
        checkpoint=None,
    ):
        source_id = parse_business_id(source_id)
        parent_id = parse_business_id(parent_id) if parent_id is not None else None
        if not request_id or len(request_id) > 128:
            raise CollectionConflict('request_id 必须为 1～128 字符')
        source = await cls.source(db, source_id, lock=True)
        previous = (await db.execute(select(Run).where(Run.request_id == request_id))).scalars().first()
        if previous:
            # An idempotent manual replay is independent of later source edits.
            if (previous.source_id, previous.trigger_type, previous.parent_id) != (source_id, trigger_type, parent_id):
                raise CollectionConflict('request_id 已被其他请求使用')
            await db.commit()
            return previous
        if not source.is_enabled:
            raise CollectionConflict('数据源已停用')
        if trigger_type not in ('manual', 'schedule', 'retry') or (
            (trigger_type == 'retry') != (parent_id is not None)
        ):
            raise CollectionConflict('触发类型与 parent_id 不匹配')
        if parent_id is not None:
            parent = await cls.run(db, parent_id)
            if parent.source_id != source_id or parent.status != 'failed':
                raise CollectionConflict('重试父记录必须是同来源的 failed 运行')
            child = (await db.execute(select(Run).where(Run.parent_id == parent_id))).scalars().first()
            if child:
                await db.commit()
                return child
            if snapshot != parent.config_snapshot:
                raise CollectionConflict('重试必须沿用父运行配置')
        active = await cls.active(db, source_id)
        if active:
            await db.commit()
            return active
        run = Run(
            source_id=source_id,
            parent_id=parent_id,
            request_id=request_id,
            trigger_type=trigger_type,
            status='queued',
            available_at=available_at or now,
            config_snapshot=deepcopy(snapshot),
            checkpoint=deepcopy(checkpoint or {}),
            fetched_count=0,
            saved_count=0,
            failed_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Cross-source request_id races are resolved by the global unique key.
            previous = (await db.execute(select(Run).where(Run.request_id == request_id))).scalars().first()
            if previous and (previous.source_id, previous.trigger_type, previous.parent_id) == (
                source_id,
                trigger_type,
                parent_id,
            ):
                await db.commit()
                return previous
            raise CollectionConflict('入队冲突，请使用新的 request_id') from None
        return run

    @classmethod
    @write_operation
    async def set_enabled(cls, db, source_id, enabled, *, now, next_run_at):
        source = await cls.source(db, source_id, lock=True)
        source.is_enabled = enabled
        source.next_run_at = next_run_at if enabled else None
        source.updated_at = now
        if not enabled:
            run = await cls.active(db, source_id)
            if run and run.status == 'queued':
                run.stop_requested_at = now
                cls.terminal(run, 'cancelled', now)
        await db.commit()
        return source

    @classmethod
    @write_operation
    async def claim(cls, db, run_id, *, now, lease_seconds):
        if lease_seconds <= 0:
            raise CollectionConflict('租约必须大于零')
        source, run = await cls.locked_run(db, run_id)
        if run.status != 'queued' or aware(run.available_at) > now:
            await db.commit()
            return None
        if not source.is_enabled:
            run.stop_requested_at = now
            cls.terminal(run, 'cancelled', now)
            await db.commit()
            return None
        run.status, run.started_at, run.updated_at = 'running', now, now
        run.execution_token = uuid4().hex
        run.lease_expires_at = now + timedelta(seconds=lease_seconds)
        await db.commit()
        return run

    @classmethod
    @write_operation
    async def stop(cls, db, run_id, *, now):
        _, run = await cls.locked_run(db, run_id)
        if run.status == 'queued':
            run.stop_requested_at = now
            cls.terminal(run, 'cancelled', now)
        elif run.status == 'running':
            run.status, run.stop_requested_at, run.updated_at = 'stopping', now, now
        await db.commit()
        return run

    @classmethod
    @write_operation
    async def heartbeat(cls, db, run_id, token, *, now, lease_seconds):
        if lease_seconds <= 0:
            raise CollectionConflict('租约必须大于零')
        _, run = await cls.locked_run(db, run_id)
        cls.fence(run, token, now, allow_stopping=True)
        run.lease_expires_at = now + timedelta(seconds=lease_seconds)
        run.updated_at = now
        stopping = run.status == 'stopping'
        await db.commit()
        return stopping

    @classmethod
    @write_operation
    async def finish(cls, db, run_id, token, *, now, error=None):
        _, run = await cls.locked_run(db, run_id)
        cls.fence(run, token, now, allow_stopping=True)
        if run.status == 'stopping':
            cls.terminal(run, 'cancelled', now)
        elif error or run.failed_count:
            cls.terminal(run, 'failed', now, error or run.error or '存在未成功处理的候选条目')
        else:
            cls.terminal(run, 'success', now)
        await db.commit()
        return run

    @classmethod
    @write_operation
    async def recover(cls, db, run_id, *, now, isolated=False):
        _, run = await cls.locked_run(db, run_id)
        if run.status in ('running', 'stopping') and run.lease_expires_at and aware(run.lease_expires_at) <= now:
            run.execution_token = run.lease_expires_at = None
            if run.status == 'running':
                cls.terminal(run, 'failed', now, '执行器租约过期')
            else:
                # Fencing DB writes does not prove an outstanding request exited.
                run.updated_at = now
        if run.status == 'stopping' and isolated:
            cls.terminal(run, 'cancelled', now)
        await db.commit()
        return run

    @staticmethod
    async def ready(db, now, limit=50):
        return list(
            (
                await db.execute(
                    select(Run.id)
                    .where(Run.status == 'queued', Run.available_at <= now)
                    .order_by(Run.available_at, Run.id)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def history(db, source_id=None, limit=100):
        stmt = select(Run).order_by(Run.created_at.desc(), Run.id.desc()).limit(limit)
        if source_id:
            stmt = stmt.where(Run.source_id == parse_business_id(source_id))
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def source_tasks(db):
        ranked = select(
            Run.id.label('run_id'),
            func.row_number()
            .over(
                partition_by=Run.source_id,
                order_by=(Run.created_at.desc(), Run.id.desc()),
            )
            .label('position'),
        ).subquery()
        latest = select(Run).join(ranked, Run.id == ranked.c.run_id).where(ranked.c.position == 1).subquery()
        last_run = aliased(Run, latest)
        return (
            await db.execute(
                select(Source, last_run)
                .outerjoin(last_run, Source.id == last_run.source_id)
                .order_by(Source.created_at.desc(), Source.id)
            )
        ).all()
