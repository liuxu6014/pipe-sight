"""The RuoYi naming exception must not widen into field/data changes."""

from types import SimpleNamespace

import pytest

from app.ruoyi_table_names import RUOYI_TABLE_NAMES, restore_ruoyi_names


def test_exact_twelve_framework_tables_only():
    assert RUOYI_TABLE_NAMES == {
        'users': 'sys_user', 'roles': 'sys_role', 'menus': 'sys_menu',
        'user_roles': 'sys_user_role', 'role_menus': 'sys_role_menu', 'settings': 'sys_config',
        'dict_types': 'sys_dict_type', 'dict_items': 'sys_dict_data',
        'login_logs': 'sys_logininfor', 'operation_logs': 'sys_oper_log',
        'scheduled_jobs': 'sys_job', 'job_logs': 'sys_job_log',
    }
    assert not {'news_articles', 'papers', 'ai_models', 'collection_runs'} & set(RUOYI_TABLE_NAMES)


def test_migration_needs_caller_transaction():
    with pytest.raises(RuntimeError, match='transaction'):
        restore_ruoyi_names(SimpleNamespace(in_transaction=lambda: False), manifest={})


def test_live_endpoint_requires_explicit_authority_before_sql():
    bind = SimpleNamespace(in_transaction=lambda: True,
                           engine=SimpleNamespace(url=SimpleNamespace(host='remote', port=5432)))
    with pytest.raises(RuntimeError, match='explicit'):
        restore_ruoyi_names(bind, manifest={})
