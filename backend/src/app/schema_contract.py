"""Frozen, approved schema contract shared by migrations and regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaPrerequisiteError(ValueError):
    """A data-preserving migration prerequisite needs an explicit choice."""


DEFAULT_CONTRACT_VERSION = 'v5'
FOUNDATION_TABLE_RENAMES = {
    'users': 'sys_user', 'roles': 'sys_role', 'menus': 'sys_menu',
    'user_roles': 'sys_user_role', 'role_menus': 'sys_role_menu',
    'settings': 'sys_config', 'dict_types': 'sys_dict_type', 'dict_items': 'sys_dict_data',
    'login_logs': 'sys_logininfor', 'operation_logs': 'sys_oper_log',
    'scheduled_jobs': 'sys_job', 'job_logs': 'sys_job_log',
}


def load_contract(version: str = DEFAULT_CONTRACT_VERSION) -> dict[str, Any]:
    """Runtime defaults to v5; historical revisions request their version explicitly."""
    if version not in ('v1', 'v2', 'v3', 'v4', 'v5'):
        raise ValueError(f'Unsupported schema contract version: {version}')
    path = Path(__file__).resolve().parents[2] / f'data/schema/compact-{version}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def validate_target_prerequisites(*, templates: list[dict], models: list[dict]) -> dict[str, Any]:
    """Do not invent model configuration; empty setup must remain usable.

    Model availability is required when submitting generation, not for preserving
    templates or authenticating. With multiple candidates, no arbitrary default
    may be selected on the administrator's behalf.
    """
    candidates = [m for m in models if m.get('is_enabled') and 'text_generate' in m.get('capabilities', [])]
    if templates and len(candidates) > 1:
        raise SchemaPrerequisiteError('存在多个文本模型，请为模板明确选择模型，不自动取第一条')
    model_id = candidates[0]['id'] if len(candidates) == 1 else None
    return {'default_text_model_id': model_id, 'generation_ready': model_id is not None}
