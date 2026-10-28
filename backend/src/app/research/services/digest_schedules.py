"""持久化周期简报计划及其到期派发。"""

from __future__ import annotations

import re
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.infrastructure.services.logging_support import logger
from app.intelligence.services.templates import PipelineTemplateService
from app.research.digest_policy import DIGEST_SELECTION_LIMIT
from app.research.models import research_models
from app.research.models.research_models import PipelineDigestSchedule, PipelineResearchJob
from app.research.repositories.research_repository import ResearchDao
from app.research.services.jobs import ResearchJobService
from config.database import AsyncSessionLocal
from exceptions.exception import ServiceException

SCHEDULE_LEASE_SECONDS = 5 * 60
MAX_HOUR = 23
MAX_MINUTE = 59
DECEMBER = 12
MAX_WEEKDAY = 6
MAX_MONTH_DAY = 31
SCHEDULE_WORKER_ID = f'task-worker-digest-schedule-{uuid4().hex[:12]}'
SOURCE_TYPE_MAP = {'新闻网站': 'news', '微信公众号': 'wechat'}
LOCAL_ZONE = ZoneInfo('Asia/Shanghai')
GENERATION_FIELDS = frozenset(
    {
        'direction',
        'project',
        'scenario',
        'keywords',
        'requirements',
        'outline',
        'options',
        'diagram',
        'citation_check',
    }
)
GENERATION_ALIASES = {'citationCheck': 'citation_check'}
GENERATION_OPTION_ALIASES = {
    'public_supplement': 'publicSupplement',
    'generate_images': 'generateImages',
    'summary_length': 'summaryLength',
    'item_count': 'itemCount',
    'hot_analysis': 'hotAnalysis',
    'duplicate_merge': 'duplicateMerge',
    'holiday_policy': 'holidayPolicy',
    'holiday_dates': 'holidayDates',
}
GENERATION_OPTIONS = frozenset(
    {
        'language',
        'length',
        'publicSupplement',
        'generateImages',
        'cadence',
        'summaryLength',
        'itemCount',
        'directions',
        'sources',
        'hotAnalysis',
        'duplicateMerge',
        'schedule',
        'holidayPolicy',
        'holidayDates',
    }
)
CREATE_FIELDS = frozenset(
    {
        'name',
        'template_id',
        'template_version',
        'request_id',
        'report_type',
        'frequency',
        'weekday',
        'month_day',
        'run_time',
        'is_enabled',
        'enabled',
        'schedule_time',
        'schedule_weekday',
        'schedule_month_day',
        'holiday_policy',
        'holiday_dates',
        'direction',
        'keywords',
        'requirements',
        'outline',
        'options',
        'timezone',
        'selection_config',
        'generation_config',
    }
)
CREATE_ALIASES = {
    'templateId': 'template_id',
    'templateVersion': 'template_version',
    'requestId': 'request_id',
    'reportType': 'report_type',
    'monthDay': 'month_day',
    'runTime': 'run_time',
    'isEnabled': 'is_enabled',
    'scheduleTime': 'schedule_time',
    'scheduleWeekday': 'schedule_weekday',
    'scheduleMonthDay': 'schedule_month_day',
    'holidayPolicy': 'holiday_policy',
    'holidayDates': 'holiday_dates',
    'selectionConfig': 'selection_config',
    'generationConfig': 'generation_config',
}


class DigestScheduleService:
    """让周期简报从页面选项变成可审计、可恢复的后台计划。"""

    @staticmethod
    def _selection_config(value: Any, *, keywords: Any = None, options: Any = None) -> dict[str, Any]:
        """Normalize saved and legacy filters without losing partial page criteria."""
        if value is not None and not isinstance(value, dict):
            raise ServiceException(message='选材配置必须为对象')
        config = deepcopy(value or {})
        nested = config.get('options', {})
        if not isinstance(nested, dict) or (options is not None and not isinstance(options, dict)):
            raise ServiceException(message='选材选项必须为对象')
        defaults = {**(options or {}), **nested}
        if 'keywords' not in config and keywords is not None:
            config['keywords'] = deepcopy(keywords)
        for field, option in (('category_names', 'directions'), ('source_types', 'sources')):
            if field not in config and option in defaults:
                config[field] = deepcopy(defaults[option])
        for field, maximum in (('keywords', 20), ('category_names', 10), ('source_types', 2)):
            if field not in config:
                continue
            terms = config[field]
            if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
                raise ServiceException(message=f'选材 {field} 必须为文本数组')
            if len(terms) > maximum or any(len(term) > 200 for term in terms):
                raise ServiceException(message=f'选材 {field} 数量或长度超出限制')
            config[field] = list(dict.fromkeys(term.strip() for term in terms if term.strip()))
        if 'source_types' in config:
            source_map = {'新闻网站': 'website', '微信公众号': 'wechat', 'news': 'website'}
            config['source_types'] = list(dict.fromkeys(source_map.get(term, term) for term in config['source_types']))
            if not config['source_types'] or set(config['source_types']) - {'website', 'wechat'}:
                raise ServiceException(message='来源范围须选择新闻网站或微信公众号')
        return config

    @staticmethod
    def _local_now() -> datetime:
        """用业务时区计算日历；数据库业务时间使用 UTC timestamptz。"""
        return datetime.now(LOCAL_ZONE)

    @staticmethod
    def _canonical_config(
        value: Any,
        allowed: frozenset[str],
        aliases: dict[str, str],
        label: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ServiceException(message=f'{label}必须为对象')
        result = {}
        for key, item in value.items():
            field = aliases.get(key, key)
            if field not in allowed:
                raise ServiceException(message=f'{label}不允许字段：{key}；选材、模板和任务标识由计划派发确定')
            if field in result:
                raise ServiceException(message=f'{label}字段重复或别名冲突：{key}')
            result[field] = deepcopy(item)
        return result

    @classmethod
    def _generation_config(cls, value: Any) -> dict[str, Any]:
        """Accept generation preferences only, never alternate evidence or IDs."""
        config = cls._canonical_config(value, GENERATION_FIELDS, GENERATION_ALIASES, '生成配置')
        for key in ('direction', 'project', 'scenario', 'requirements'):
            if key in config and not isinstance(config[key], str):
                raise ServiceException(message=f'生成配置 {key} 必须为文本')
        if 'keywords' in config and (
            not isinstance(config['keywords'], list) or any(not isinstance(item, str) for item in config['keywords'])
        ):
            raise ServiceException(message='生成配置 keywords 必须为文本数组')
        if 'outline' in config and (
            not isinstance(config['outline'], list) or any(not isinstance(item, dict) for item in config['outline'])
        ):
            raise ServiceException(message='生成配置 outline 必须为章节对象数组')
        for key in ('diagram', 'citation_check'):
            if key in config and not isinstance(config[key], bool):
                raise ServiceException(message=f'生成配置 {key} 必须为布尔值')
        if 'options' in config:
            options = cls._canonical_config(
                config['options'], GENERATION_OPTIONS, GENERATION_OPTION_ALIASES, '生成选项'
            )
            for key in ('generateImages', 'publicSupplement', 'hotAnalysis', 'duplicateMerge', 'schedule'):
                if key in options and not isinstance(options[key], bool):
                    raise ServiceException(message=f'生成选项 {key} 必须为布尔值')
            ResearchJobService._validate_options(options)
            config['options'] = options
        return config

    @staticmethod
    async def _validate_enabled_template(
        db: Any,
        template_id: Any,
        generation_config: dict[str, Any],
        template_service: Any,
        frequency: str | None = None,
    ) -> Any:
        template = await template_service.get_published(db, template_id)
        if not template or template.purpose != 'digest':
            raise ServiceException(message='请选择已启用的简报模板')
        if frequency is not None:
            PipelineTemplateService.validate_digest_cadence(template, frequency)
        image_config = PipelineTemplateService.effective_image_config(template.image_config, generation_config)
        await template_service.validate_models(db, template.model_id, template.image_model_id, image_config)
        return template

    @classmethod
    async def _template_for_schedule(
        cls,
        db: Any,
        template_id: int,
        generation: dict[str, Any],
        enabled: bool,
        template_service: Any,
    ) -> Any:
        if enabled:
            return await cls._validate_enabled_template(db, template_id, generation, template_service)
        template = await ResearchDao.get_template(db, template_id)
        if not template or template.purpose != 'digest':
            raise ServiceException(message='请选择有效的简报模板')
        return template

    @staticmethod
    def _parse_schedule_time(value: str) -> tuple[int, int]:
        try:
            hour_text, minute_text = value.split(':', 1)
            hour, minute = int(hour_text), int(minute_text)
        except (AttributeError, ValueError) as exc:
            raise ServiceException(message='计划执行时间必须是HH:MM格式') from exc
        if not (0 <= hour <= MAX_HOUR and 0 <= minute <= MAX_MINUTE):
            raise ServiceException(message='计划执行时间必须是有效的本地时间')
        return hour, minute

    @classmethod
    def _base_next_occurrence(
        cls,
        reference: datetime,
        report_type: str,
        schedule_time: str,
        *,
        schedule_weekday: int = 0,
        schedule_month_day: int = 1,
    ) -> datetime:
        hour, minute = cls._parse_schedule_time(schedule_time)
        candidate = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if report_type == 'daily':
            return candidate + timedelta(days=1) if candidate <= reference else candidate
        if report_type == 'weekly':
            days_until_selected = (schedule_weekday - candidate.weekday()) % 7
            candidate += timedelta(days=days_until_selected)
            return candidate + timedelta(days=7) if candidate <= reference else candidate
        if report_type == 'monthly':
            candidate = candidate.replace(day=min(schedule_month_day, monthrange(candidate.year, candidate.month)[1]))
            if candidate <= reference:
                candidate = candidate.replace(day=1)
                if candidate.month == DECEMBER:
                    candidate = candidate.replace(year=candidate.year + 1, month=1)
                else:
                    candidate = candidate.replace(month=candidate.month + 1)
                return candidate.replace(day=min(schedule_month_day, monthrange(candidate.year, candidate.month)[1]))
            return candidate
        raise ServiceException(message='不支持的周期简报类型')

    @staticmethod
    def _schedule_days(config: dict[str, Any]) -> dict[str, int]:
        return {
            'schedule_weekday': config.get('schedule_weekday', config.get('scheduleWeekday', 0)),
            'schedule_month_day': config.get('schedule_month_day', config.get('scheduleMonthDay', 1)),
        }

    @staticmethod
    def _holiday_policy(config: dict[str, Any]) -> str:
        options = dict(config.get('options') or {})
        value = config.get('holiday_policy') or config.get('holidayPolicy') or options.get('holidayPolicy') or 'run'
        if value not in {'run', 'skip'}:
            raise ServiceException(message='节假日策略只能选择继续执行或跳过')
        return value

    @staticmethod
    def _holiday_dates(config: dict[str, Any]) -> frozenset[date]:
        options = dict(config.get('options') or {})
        raw_values = config.get('holiday_dates') or config.get('holidayDates') or options.get('holidayDates') or []
        if isinstance(raw_values, str):
            raw_values = [item.strip() for item in raw_values.split(',') if item.strip()]
        dates = {DigestScheduleService._parse_holiday_date(value) for value in raw_values}
        return frozenset(dates)

    @staticmethod
    def _parse_holiday_date(value: Any) -> date:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise ServiceException(message=f'节假日日期格式无效：{value}，必须是YYYY-MM-DD') from exc

    @classmethod
    def _next_occurrence(
        cls,
        reference: datetime,
        report_type: str,
        schedule_time: str,
        *,
        schedule_weekday: int = 0,
        schedule_month_day: int = 1,
        holiday_policy: str = 'run',
        holiday_dates: frozenset[date] | set[date] = frozenset(),
    ) -> datetime:
        days = {'schedule_weekday': schedule_weekday, 'schedule_month_day': schedule_month_day}
        candidate = cls._base_next_occurrence(reference, report_type, schedule_time, **days)
        if holiday_policy == 'run' or not holiday_dates:
            return candidate
        while candidate.date() in holiday_dates:
            candidate = cls._base_next_occurrence(candidate, report_type, schedule_time, **days)
        return candidate

    @staticmethod
    def _period_for_run(run_at: datetime, report_type: str) -> list[str]:
        if report_type == 'daily':
            day = run_at.date() - timedelta(days=1)
            return [day.isoformat()]
        if report_type == 'weekly':
            end = run_at.date() - timedelta(days=1)
            start = end - timedelta(days=6)
            return [start.isoformat(), end.isoformat()]
        first_this_month = run_at.date().replace(day=1)
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
        return [start.isoformat(), end.isoformat()]

    @staticmethod
    def _datetime_text(value: datetime | None) -> str:
        return value.strftime('%Y-%m-%d %H:%M:%S') if value else ''

    @classmethod
    def serialize(cls, row: Any, *, latest_job=None, report=None) -> dict[str, Any]:
        last_run = getattr(row, 'last_run_at', None)
        state = getattr(row, 'last_status', None)
        error = cls.safe_error(getattr(row, 'last_error', None))
        # 派发与任务入队同事务：非 queued 摘要优先，不能被旧成果覆盖。
        job_current = latest_job is not None and state in (None, 'queued')
        job = latest_job if job_current else None
        if job:
            state = job.status
            last_run = last_run or job.started_at or job.created_at
            error = cls.safe_error(job.error)
        has_result = bool(job and job.status == 'completed' and report and (report.content or '').strip())
        return {
            'id': wire_id(row.id),
            'scheduleId': wire_id(row.id),
            'name': row.name,
            'reportType': row.frequency,
            'digestCadence': row.frequency,
            'templateId': wire_id(row.template_id),
            'scheduleTime': row.run_time.isoformat(),
            'scheduleWeekday': row.weekday,
            'scheduleMonthDay': row.month_day,
            'timezone': row.timezone,
            'enabled': row.is_enabled,
            'nextRunTime': row.next_run_at.isoformat() if row.next_run_at else '',
            'config': row.selection_config,
            'generationConfig': row.generation_config,
            'lastStatus': state or 'never',
            'lastRunTime': format_business_time(last_run),
            'lastError': error,
            'matchedCount': len(job.materials or []) if job else (0 if state == 'no_data' else None),
            'latestTaskId': wire_id(job.id) if job else '',
            'latestReportId': wire_id(report.id) if has_result else '',
            'hasResult': has_result,
            'canDelete': latest_job is None,
        }

    @staticmethod
    def safe_error(message):
        text = str(message or '')
        text = re.sub(r'(?i)\bBearer\s+\S+|\bsk-[a-zA-Z0-9_-]+', '[已隐藏密钥]', text)
        text = re.sub(r'(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+', r'\1[已隐藏]', text)
        text = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[已隐藏]@', text)
        return text[:2000]

    @classmethod
    def next_run(cls, row: Any, reference: datetime) -> datetime:
        local = ResearchDao.aware(reference).astimezone(ZoneInfo(row.timezone))
        config = row.selection_config or {}
        result = cls._next_occurrence(
            local - timedelta(seconds=row.run_time.second, microseconds=row.run_time.microsecond),
            row.frequency,
            row.run_time.strftime('%H:%M'),
            schedule_weekday=row.weekday if row.weekday is not None else 0,
            schedule_month_day=row.month_day if row.month_day is not None else 1,
            holiday_policy=cls._holiday_policy(config),
            holiday_dates=cls._holiday_dates(config),
        )
        return (result + timedelta(seconds=row.run_time.second, microseconds=row.run_time.microsecond)).astimezone(
            timezone.utc
        )

    @classmethod
    async def _prepare(
        cls,
        db: Any,
        *,
        user_id: int,
        owner_name: str,
        payload: Any,
        template_service: Any,
    ) -> dict[str, Any]:
        data = payload.model_dump(by_alias=False) if hasattr(payload, 'model_dump') else payload
        data = cls._canonical_config(data, CREATE_FIELDS, CREATE_ALIASES, '自动计划')
        raw_generation = data.get('generation_config')
        generation = cls._generation_config(
            {
                'requirements': data.get('requirements', ''),
                'direction': data.get('direction', ''),
                'outline': data.get('outline', []),
                'options': data.get('options', {}),
            }
            if raw_generation is None or raw_generation == {}
            else raw_generation
        )
        enabled = data.get('is_enabled', data.get('enabled', True))
        if not isinstance(enabled, bool):
            raise ServiceException(message='计划启停值必须为布尔值')
        template_id = parse_business_id(data['template_id'])
        template = await cls._template_for_schedule(db, template_id, generation, enabled, template_service)
        frequency = data.get('frequency') or data.get('report_type')
        if frequency not in {'daily', 'weekly', 'monthly'}:
            raise ServiceException(message='计划频率不合法')
        PipelineTemplateService.validate_digest_cadence(template, frequency)
        weekday = data.get('weekday', data.get('schedule_weekday', 0)) if frequency == 'weekly' else None
        month_day = data.get('month_day', data.get('schedule_month_day', 1)) if frequency == 'monthly' else None
        if (weekday is not None and not 0 <= weekday <= MAX_WEEKDAY) or (
            month_day is not None and not 1 <= month_day <= MAX_MONTH_DAY
        ):
            raise ServiceException(message='执行星期或日期不合法')
        zone = data.get('timezone', 'Asia/Shanghai')
        try:
            ZoneInfo(zone)
            run_time = time.fromisoformat(data.get('run_time') or data.get('schedule_time', '08:00'))
        except (ValueError, KeyError):
            raise ServiceException(message='计划时区或执行时间不合法') from None
        row = PipelineDigestSchedule(
            user_id=user_id,
            name=data['name'],
            template_id=template.id,
            frequency=frequency,
            weekday=weekday,
            month_day=month_day,
            run_time=run_time,
            timezone=zone,
            selection_config=cls._selection_config(
                data.get('selection_config'), keywords=data.get('keywords', []), options=data.get('options', {})
            ),
            generation_config=generation,
            is_enabled=enabled,
        )
        for field in ('options', 'holiday_policy', 'holiday_dates'):
            if field in data:
                row.selection_config.setdefault(field, deepcopy(data[field]))
        # 只规范已定义的实体引用，不递归猜测提示词、正文、章节 ID 或 token。
        for config in (row.selection_config,):
            for field in ('source_ids', 'category_ids', 'selected_item_ids'):
                if field in config:
                    config[field] = [wire_id(value) for value in config[field]]
            for field in ('template_id', 'report_id', 'model_id', 'image_model_id'):
                if config.get(field) is not None:
                    config[field] = wire_id(config[field])
            if 'materials' in config:
                config['materials'] = [{**item, 'id': wire_id(item['id'])} for item in config['materials']]
        return row

    @classmethod
    async def create(cls, db, *, user_id, owner_name, payload, template_service):
        row = await cls._prepare(db, user_id=user_id, owner_name=owner_name, payload=payload,
                                 template_service=template_service)
        enabled = row.is_enabled
        row.next_run_at = cls.next_run(row, research_models.utcnow()) if enabled else None
        await ResearchDao.add_digest_schedule(db, row)
        await db.commit()
        return cls.serialize(row)

    @classmethod
    async def update(cls, db, *, user_id, schedule_id, payload, template_service):
        row = await ResearchDao.lock_digest_schedule_for_update(db, schedule_id, user_id)
        if not row:
            raise ServiceException(message='自动计划不存在或无权访问')
        # Validate a detached candidate before changing the locked persistent row.
        candidate = await cls._prepare(db, user_id=user_id, owner_name='', payload=payload,
                                       template_service=template_service)
        for field in ('name', 'template_id', 'frequency', 'weekday', 'month_day', 'run_time', 'timezone',
                      'selection_config', 'generation_config', 'is_enabled'):
            setattr(row, field, getattr(candidate, field))
        row.next_run_at = cls.next_run(row, research_models.utcnow()) if row.is_enabled else None
        await db.commit()
        return cls.serialize(row)

    @classmethod
    async def list(cls, db: Any, user_id: int) -> dict[str, Any]:
        rows = await ResearchDao.list_digest_schedules(db, user_id)
        history = await ResearchDao.latest_schedule_jobs(db, user_id, [row.id for row in rows])
        return {'rows': [cls.serialize(row, latest_job=history.get(row.id, (None,None))[0],
            report=history.get(row.id, (None,None))[1]) for row in rows], 'total': len(rows)}

    @classmethod
    async def set_enabled(
        cls,
        db: Any,
        user_id: int,
        schedule_id: str | int,
        enabled: bool,
    ) -> dict[str, Any]:
        row = await ResearchDao.lock_digest_schedule_for_update(db, schedule_id, user_id)
        if not row:
            raise ServiceException(message='自动计划不存在或无权访问')
        if not isinstance(enabled, bool):
            raise ServiceException(message='计划启停值必须为布尔值')
        if enabled:
            generation = cls._generation_config(row.generation_config if row.generation_config is not None else {})
            await cls._validate_enabled_template(
                db, row.template_id, generation, PipelineTemplateService, frequency=row.frequency
            )
        row.is_enabled = enabled
        row.next_run_at = cls.next_run(row, research_models.utcnow()) if enabled else None
        await db.commit()
        return cls.serialize(row)

    @classmethod
    async def run_now(cls, db: Any, user_id: int, schedule_id: str | int) -> dict[str, Any]:
        row = await ResearchDao.lock_digest_schedule_for_update(db, schedule_id, user_id)
        if not row or not row.is_enabled:
            raise ServiceException(message='计划不存在、无权访问或已停用')
        generation = cls._generation_config(row.generation_config if row.generation_config is not None else {})
        await cls._validate_enabled_template(
            db, row.template_id, generation, PipelineTemplateService, frequency=row.frequency
        )
        row.next_run_at = research_models.utcnow()
        await db.commit()
        return cls.serialize(row)

    @staticmethod
    async def delete(db: Any, user_id: int, schedule_id: str | int) -> None:
        schedule_id = parse_business_id(schedule_id)
        row = await ResearchDao.lock_digest_schedule_for_update(db, schedule_id, user_id)
        if not row:
            raise ServiceException(message='自动计划不存在或无权访问')
        # 历史任务 schedule_id RESTRICT，不硬删有历史的计划。
        if await db.scalar(
            select(PipelineResearchJob.id).where(PipelineResearchJob.schedule_id == schedule_id).limit(1)
        ):
            raise ServiceException(message='计划已有生成历史，请停用而非删除')
        await db.delete(row)
        await db.commit()

    @classmethod
    async def dispatch_due(
        cls,
        *,
        stage_labels: Any,
        job_serializer: Any,
        template_service: Any,
        schedule_ids=None,
    ) -> dict[str, int]:
        result = {'found': 0, 'queued': 0, 'no_data': 0, 'skipped': 0, 'failed': 0}
        if AsyncSessionLocal is None:
            return result
        # 同一事务内锁计划、选材、入队、推进游标，避免提前 commit 释放认领。
        async with AsyncSessionLocal() as db:
            scope = {'schedule_ids': schedule_ids} if schedule_ids is not None else {}
            schedules = await ResearchDao.list_due_schedules(db, research_models.utcnow(), **scope)
            result['found'] = len(schedules)
            for row in schedules:
                checked_at = research_models.utcnow().replace(microsecond=0)
                try:
                    async with db.begin_nested():
                        generation = cls._generation_config(
                            row.generation_config if row.generation_config is not None else {}
                        )
                        run_at = ResearchDao.aware(row.next_run_at)
                        local = run_at.astimezone(ZoneInfo(row.timezone))
                        config = cls._selection_config(
                            row.selection_config, keywords=generation.get('keywords'), options=generation.get('options')
                        )
                        if cls._holiday_policy(config) == 'skip' and local.date() in cls._holiday_dates(config):
                            result['skipped'] += 1
                            status = 'skipped'
                        else:
                            await cls._validate_enabled_template(
                                db, row.template_id, generation, template_service, frequency=row.frequency
                            )
                            period = cls._period_for_run(local, row.frequency)
                            start = datetime.fromisoformat(period[0]).replace(tzinfo=ZoneInfo(row.timezone))
                            end = datetime.fromisoformat(period[-1]).replace(tzinfo=ZoneInfo(row.timezone)) + timedelta(
                                days=1
                            )
                            candidates = await ResearchDao.digest_candidates(db, start, end, config)
                            unique, seen = [], set()
                            for item in candidates:
                                key = ' '.join(item.title.split()).casefold()
                                if key in seen or not (item.content_zh or item.content or '').strip():
                                    continue
                                seen.add(key)
                                unique.append(item)
                            limit = int(config.get('limit', config.get('options', {}).get('itemCount', 10)))
                            if not 1 <= limit <= DIGEST_SELECTION_LIMIT:
                                raise ServiceException(message='自动选材上限须为 1 至 50')
                            if not unique:
                                result['no_data'] += 1
                                status = 'no_data'
                            else:
                                data = {
                                    **generation,
                                    'requirements': cls._requirements_for_period(generation, period),
                                    'keywords': deepcopy(config.get('keywords', generation.get('keywords', []))),
                                    'title': f'{row.name} {period[0]}',
                                    'report_type': row.frequency,
                                    'template_id': wire_id(row.template_id),
                                    'selected_item_ids': [wire_id(i.id) for i in unique[:limit]],
                                    'request_id': f'schedule:{row.id}:{run_at.isoformat()}',
                                    'period': period,
                                    'selection_strategy': {
                                        'candidate_count': len(unique),
                                        'limit': limit,
                                        'dedup': 'normalized_title',
                                    },
                                }
                                await ResearchJobService.queue(
                                    db,
                                    user_id=row.user_id,
                                    owner_name='',
                                    payload=data,
                                    stage_labels=stage_labels,
                                    job_serializer=job_serializer,
                                    template_service=template_service,
                                    schedule_id=row.id,
                                    commit=False,
                                )
                                result['queued'] += 1
                                status = 'queued'
                        row.next_run_at = cls.next_run(row, run_at)
                        row.last_run_at, row.last_status, row.last_error = checked_at, status, None
                except Exception as exc:
                    result['failed'] += 1
                    # 保存摘要，但保留原游标；保存点回滚不抹掉失败原因。
                    row.last_run_at, row.last_status = checked_at, 'failed'
                    row.last_error = cls.safe_error(getattr(exc, 'message', None)) or f'计划派发异常（{type(exc).__name__}），请联系管理员检查任务日志。'
                    logger.exception('周期简报派发失败；计划游标未推进')
            await db.commit()
        return result

    @staticmethod
    def _requirements_for_period(generation: dict, period: list[str]) -> str:
        """重建旧 UI 自动拼接的周期条款，保留用户其余要求及选材偏好。"""
        text = generation.get('requirements', '')
        current = f'报告周期：{period[0]} 至 {period[-1]}'
        # 仅替换已知 UI 周期条款，不删除自由要求中的历史事实日期。
        pattern = r'报告周期\s*[:：][^；;\n]*'
        if re.search(pattern, text):
            return re.sub(pattern, lambda _: current, text)
        return current + (f'；{text}' if text else '')
