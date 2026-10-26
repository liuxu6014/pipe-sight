"""受控异步适配器执行器：分批、协作停止、超时和数据库令牌隔离。"""

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import parse_qsl, urlsplit

from app.business_ids import parse_business_id, wire_id
from app.intelligence.integrations.public_source_bridge import register_builtin_adapters
from app.intelligence.repositories.collection_repository import CollectionRepository, LeaseLost
from app.intelligence.services.collection_persistence import CollectionPersistenceService
from app.intelligence.services.collection_translation import (
    CollectionTranslationService,
    TranslationConfigurationError,
    TranslationFailure,
)


class ConfigurationError(ValueError):
    pass


class TransientCollectionError(RuntimeError):
    """适配器仅用此异常声明临时端点/会话故障；异常文本不写入运行。"""


@dataclass(frozen=True)
class CollectionBatch:
    records: list
    checkpoint: dict


@dataclass(frozen=True)
class Adapter:
    # factory(snapshot, checkpoint) -> async iterator[CollectionBatch]. Each yield
    # is a bounded page/request boundary. Cancellation must release resources.
    factory: object
    source_types: tuple
    allowed_hosts: tuple = ()
    supports_resume: bool = False
    validate_config: object = None


class AdapterRegistry:
    def __init__(self):
        self.adapters = {}

    def register(self, name, adapter):
        if not name or name in self.adapters:
            raise ConfigurationError('适配器标识为空或已注册')
        self.adapters[name] = adapter

    def get(self, name):
        if name not in self.adapters:
            raise ConfigurationError('适配器未注册；须由后台安装受控实现')
        return self.adapters[name]

    def validate(self, snapshot):
        adapter = self.get(snapshot['adapter'])
        if snapshot['type'] not in adapter.source_types:
            raise ConfigurationError('适配器与来源类型不匹配')
        if snapshot.get('url'):
            try:
                url = urlsplit(snapshot['url'])
                port = url.port
            except (ValueError, TypeError) as exc:
                raise ConfigurationError('无效来源 URL') from exc
            if (
                url.scheme != 'https'
                or url.hostname not in adapter.allowed_hosts
                or url.username
                or url.password
                or port not in (None, 443)
            ):
                raise ConfigurationError('来源 URL 不在适配器 HTTPS 白名单')
            if any(
                key.lower().replace('-', '_') in {'token', 'api_key', 'apikey', 'secret', 'password'}
                for key, _ in parse_qsl(url.query)
            ):
                raise ConfigurationError('来源 URL 只允许公开入口，不保存明文凭证')
        validate_config(snapshot['config'])
        if adapter.validate_config is not None:
            adapter.validate_config(snapshot)
        return adapter


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigurationError('config 必须是对象')
    if set(config) & {'adapter', 'cron', 'timezone'}:
        raise ConfigurationError('config 不得重复 adapter/cron/timezone')

    # Credentials are resolved privately by an adapter; snapshots carry refs only.
    def check(value):
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = key.lower().replace('-', '_')
                if normalized in {
                    'password',
                    'api_key',
                    'apikey',
                    'secret',
                    'token',
                    'cookie',
                    'authorization',
                    'headers',
                }:
                    raise ConfigurationError('配置只允许凭证引用，不保存明文认证信息')
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(config)
    for key, default, upper in (('request_timeout', 30, 120), ('total_timeout', 300, 3600)):
        value = config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= upper:
            raise ConfigurationError('采集超时超出有效范围')
    retry = config.get('retry', {})
    if not isinstance(retry, dict) or set(retry) - {'enabled', 'max_retries', 'backoff_seconds', 'max_backoff_seconds'}:
        raise ConfigurationError('retry 策略无效')
    if not isinstance(retry.get('enabled', False), bool):
        raise ConfigurationError('retry.enabled 必须为布尔值')
    for key, default, maximum in (
        ('max_retries', 0, 20),
        ('backoff_seconds', 30, 86400),
        ('max_backoff_seconds', 3600, 604800),
    ):
        value = retry.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ConfigurationError('retry 次数或退避无效')


ADAPTERS = AdapterRegistry()
# Only registration occurs here: no HTTP request, DB access or source bootstrap.
# Existing public collectors use an async transport bridge, not urllib threads.
register_builtin_adapters(ADAPTERS)


def classification_session_factory(db):
    """Dedicated sessions: the collector's source/run locks never reach a model call."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(bind=db.bind, expire_on_commit=False, autoflush=False)


class PipelineCollectionService:
    @classmethod
    async def prepare_records(cls, db, records, snapshot):
        # The outer execute loop keeps heartbeats alive and cancels this task on stop.
        translated = await CollectionTranslationService.translate(classification_session_factory(db), snapshot, records)
        classifications = await cls.classify_records(db, translated, 'paper' if snapshot['type'] == 'paper' else 'news')
        return translated, classifications

    @staticmethod
    async def classify_records(db, records, kind):
        from app.intelligence.services.categories import CategoryService

        results = []
        sessions = classification_session_factory(db)
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get('title'), str) or not record['title'].strip():
                results.append((None, True))
                continue
            if kind == 'paper':
                content = json.dumps(
                    {
                        key: record.get(key)
                        for key in ('doi', 'authors', 'journal', 'published_date', 'abstract', 'abstract_zh')
                    },
                    ensure_ascii=False,
                )
            else:
                content = record.get('content_zh') or record.get('content') or ''
            async with sessions() as classification_db:
                try:
                    # Always call the real category service, including an empty
                    # or disabled-only category set. No adapter-registry shortcut.
                    category_id = await CategoryService.classify(
                        classification_db, title=record['title'], content=content, kind=kind
                    )
                    await classification_db.commit()
                    results.append((category_id, False))
                except Exception:
                    await classification_db.rollback()
                    results.append((None, True))
        return results

    @classmethod
    async def execute(cls, db, run_id, *, registry=ADAPTERS, clock=None, lease_seconds=90, pulse_seconds=5):
        run_id = parse_business_id(run_id)
        clock = clock or (lambda: datetime.now(timezone.utc))
        if not 0 < pulse_seconds < lease_seconds / 2:
            raise ValueError('心跳间隔必须小于租约的一半')
        run = await CollectionRepository.claim(db, run_id, now=clock(), lease_seconds=lease_seconds)
        if not run:
            return {'id': wire_id(run_id), 'status': 'skipped'}
        token = run.execution_token
        snapshot, checkpoint = deepcopy(run.config_snapshot), deepcopy(run.checkpoint)
        iterator = pending = None
        error = None
        fenced = False
        try:
            adapter = registry.validate(snapshot)
            iterator = adapter.factory(snapshot, checkpoint if adapter.supports_resume else {}).__aiter__()
            deadline = monotonic() + snapshot['config'].get('total_timeout', 300)
            while True:
                stopping = await CollectionRepository.heartbeat(
                    db, run_id, token, now=clock(), lease_seconds=lease_seconds
                )
                if stopping:
                    break
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError
                request_deadline = monotonic() + min(remaining, snapshot['config'].get('request_timeout', 30))
                pending = asyncio.create_task(anext(iterator))
                while not pending.done():
                    remaining = request_deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    done, _ = await asyncio.wait([pending], timeout=min(pulse_seconds, remaining))
                    stopping = await CollectionRepository.heartbeat(
                        db, run_id, token, now=clock(), lease_seconds=lease_seconds
                    )
                    if stopping:
                        break
                    if done:
                        break
                if stopping:
                    break
                try:
                    batch = pending.result()
                except StopAsyncIteration:
                    break
                pending = None
                if (
                    not isinstance(batch, CollectionBatch)
                    or not isinstance(batch.records, list)
                    or len(batch.records) > 500
                ):
                    raise ConfigurationError('适配器批次无效或超过 500 条')
                if not isinstance(batch.checkpoint, dict):
                    raise ConfigurationError('checkpoint 必须为对象')
                # Checkpoints are bounded cursors, never copies of article bodies.
                if len(json.dumps(batch.checkpoint).encode()) > 8192 or set(batch.checkpoint) - {
                    'cursor',
                    'page',
                    'last_id',
                }:
                    raise ConfigurationError('断点仅允许有界 cursor/page/last_id')
                if any(
                    value is not None and (isinstance(value, bool) or not isinstance(value, (str, int)))
                    for value in batch.checkpoint.values()
                ):
                    raise ConfigurationError('断点只允许标量游标，不保存材料正文或对象')
                classifications = []
                records = batch.records
                if batch.records:
                    pending = asyncio.create_task(cls.prepare_records(db, batch.records, snapshot))
                    while not pending.done():
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            raise TimeoutError
                        await asyncio.wait([pending], timeout=min(pulse_seconds, remaining))
                        stopping = await CollectionRepository.heartbeat(
                            db, run_id, token, now=clock(), lease_seconds=lease_seconds
                        )
                        if stopping:
                            break
                    if stopping:
                        break
                    records, classifications = pending.result()
                    pending = None
                await CollectionPersistenceService.save_batch(
                    db,
                    run_id,
                    token,
                    records,
                    batch.checkpoint,
                    now=clock(),
                    supports_resume=adapter.supports_resume,
                    clock=clock,
                    classifications=classifications,
                )
        except LeaseLost:
            await db.rollback()
            current = await CollectionRepository.run(db, run_id)
            # A stop racing the batch write is acknowledged only after cleanup.
            if current.status != 'stopping' or current.execution_token != token:
                fenced = True
        except TranslationFailure:
            error = '候选条目自动翻译失败，请检查模型后重试'
        except (TimeoutError, TransientCollectionError):
            error = '临时采集故障或请求超时'
        except (ConfigurationError, TranslationConfigurationError):
            error = '采集配置或凭证无效，请修复后新建手动运行'
        except asyncio.CancelledError:
            # Worker shutdown isn't a user stop. Persist failure after releasing
            # resources; the old token can never commit into a replacement run.
            error = '执行器中断'
        except Exception:
            error = '采集执行异常，请检查适配器'
        finally:
            if pending is not None:
                pending.cancel()
                done, _ = await asyncio.wait([pending], timeout=min(5, pulse_seconds))
                if done:
                    await asyncio.gather(pending, return_exceptions=True)
                else:
                    fenced = True
                    # No cancellation acknowledgment: leave stopping visible.
                    pending.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
            if iterator is not None and hasattr(iterator, 'aclose') and (pending is None or pending.done()):
                try:
                    await asyncio.wait_for(iterator.aclose(), timeout=min(5, pulse_seconds))
                except (Exception, asyncio.CancelledError):
                    error = '适配器资源释放失败'
                    fenced = True  # Cannot claim a confirmed cancellation.
        if fenced:
            await db.rollback()
            return {'id': wire_id(run_id), 'status': 'fenced'}
        try:
            result = await CollectionRepository.finish(db, run_id, token, now=clock(), error=error)
        except LeaseLost:
            await db.rollback()
            return {'id': wire_id(run_id), 'status': 'fenced'}
        if result.status == 'failed':
            from app.intelligence.services.sources import IntelligenceSourceService

            await IntelligenceSourceService.retry_collection_run(
                db, run_id, automatic=True, registry=registry, clock=clock
            )
        return {'id': wire_id(run_id), 'status': result.status}
