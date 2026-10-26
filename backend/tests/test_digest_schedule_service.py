"""规范周期计划：选定星期/月日、短月、时区与持久筛选。"""

from datetime import datetime, timezone

import pytest
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network
from test_research_simplified_20261025 import raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.parametrize(
    'frequency,expected',
    [('daily', datetime(2026, 10, 4, 8)), ('weekly', datetime(2026, 10, 5, 8)), ('monthly', datetime(2026, 11, 1, 8))],
)
def test_next_occurrence_boundaries(env, frequency, expected):
    assert (
        env.schedules.DigestScheduleService._next_occurrence(datetime(2026, 10, 3, 9), frequency, '08:00') == expected
    )


@pytest.mark.parametrize(
    'reference,month_day,expected',
    [
        (datetime(2026, 10, 3, 9), 15, datetime(2026, 10, 15, 8)),
        (datetime(2026, 10, 15, 8), 15, datetime(2026, 11, 15, 8)),
        (datetime(2026, 1, 31, 9), 31, datetime(2026, 2, 28, 8)),
        (datetime(2028, 2, 1, 9), 31, datetime(2028, 2, 29, 8)),
        (datetime(2026, 2, 28, 8), 31, datetime(2026, 3, 31, 8)),
        (datetime(2026, 12, 31, 8), 31, datetime(2027, 1, 31, 8)),
    ],
)
def test_monthly_selected_day_and_short_month(env, reference, month_day, expected):
    assert (
        env.schedules.DigestScheduleService._next_occurrence(
            reference, 'monthly', '08:00', schedule_month_day=month_day
        )
        == expected
    )


@pytest.mark.parametrize(
    'reference,weekday,expected',
    [
        (datetime(2026, 10, 3, 9), 6, datetime(2026, 10, 4, 8)),
        (datetime(2026, 10, 4, 7), 6, datetime(2026, 10, 4, 8)),
        (datetime(2026, 10, 4, 8), 6, datetime(2026, 10, 11, 8)),
    ],
)
def test_weekly_selected_weekday(env, reference, weekday, expected):
    assert (
        env.schedules.DigestScheduleService._next_occurrence(reference, 'weekly', '08:00', schedule_weekday=weekday)
        == expected
    )


def test_holiday_skip_preserves_month_day(env):
    assert env.schedules.DigestScheduleService._next_occurrence(
        datetime(2026, 1, 31, 9),
        'monthly',
        '08:00',
        schedule_month_day=31,
        holiday_policy='skip',
        holiday_dates={datetime(2026, 2, 28).date()},
    ) == datetime(2026, 3, 31, 8)


def test_invalid_holiday_dates_are_rejected(env):
    with raises(env, 'YYYY-MM-DD'):
        env.schedules.DigestScheduleService._holiday_dates({'holidayDates': ['国庆节']})


def test_period_is_complete_previous_digest_window(env):
    service = env.schedules.DigestScheduleService
    run = datetime(2026, 10, 5, 8)
    assert service._period_for_run(run, 'daily') == ['2026-10-04']
    assert service._period_for_run(run, 'weekly') == ['2026-09-28', '2026-10-04']
    assert service._period_for_run(run, 'monthly') == ['2026-09-01', '2026-09-30']


@pytest.mark.asyncio
async def test_create_persists_canonical_fields_and_legacy_selection_options(env, db, monkeypatch):
    template, _ = seed(env, db)
    template.purpose = 'digest'
    await db.commit()
    now = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(env.models, 'utcnow', lambda: now)
    result = await env.schedules.DigestScheduleService.create(
        db,
        user_id=7,
        owner_name='用户',
        payload={
            'name': '周报',
            'report_type': 'weekly',
            'template_id': '201',
            'schedule_time': '08:00',
            'schedule_weekday': 4,
            'options': {'sources': ['新闻网站'], 'directions': ['检测技术'], 'itemCount': 5},
        },
        template_service=env.template.PipelineTemplateService,
    )
    row = (await env.repo.ResearchDao.list_digest_schedules(db, 7))[0]
    assert row.weekday == 4 and row.month_day is None and row.frequency == 'weekly'
    assert row.selection_config['source_types'] == ['website'] and row.selection_config['category_names'] == [
        '检测技术'
    ]
    assert result['nextRunTime'].startswith('2026-10-09T00:00:00')
    assert not hasattr(row, 'request_id')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'frequency,field,value',
    [
        ('weekly', 'schedule_weekday', -1),
        ('weekly', 'schedule_weekday', 7),
        ('monthly', 'schedule_month_day', 0),
        ('monthly', 'schedule_month_day', 32),
    ],
)
async def test_create_rejects_invalid_calendar_fields(env, db, frequency, field, value):
    template, _ = seed(env, db)
    template.purpose = 'digest'
    await db.commit()
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.create(
            db,
            user_id=7,
            owner_name='用户',
            payload={'name': '计划', 'report_type': frequency, 'template_id': '201', field: value},
            template_service=env.template.PipelineTemplateService,
        )


@pytest.mark.asyncio
async def test_schedule_is_private_and_disable_clears_cursor(env, db):
    template, _ = seed(env, db)
    template.purpose = 'digest'
    await db.commit()
    row = await env.schedules.DigestScheduleService.create(
        db,
        user_id=7,
        owner_name='用户',
        payload={'name': '日报', 'report_type': 'daily', 'template_id': '201'},
        template_service=env.template.PipelineTemplateService,
    )
    with raises(env, '无权'):
        await env.schedules.DigestScheduleService.set_enabled(db, 8, row['id'], False)
    result = await env.schedules.DigestScheduleService.set_enabled(db, 7, row['id'], False)
    assert not result['enabled'] and result['nextRunTime'] == ''
