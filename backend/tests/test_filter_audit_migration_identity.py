"""Compatibility views expose business keys, never PostgreSQL physical CTIDs."""

import importlib.util
from pathlib import Path

import pytest


def test_filter_audit_uses_full_stable_news_key(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261003_normalize_filter_audit.py'
    spec = importlib.util.spec_from_file_location('filter_audit_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []
    monkeypatch.setattr(module.op, 'execute', lambda statement: statements.append(str(statement)))
    module.upgrade()
    assert len(statements) == 1
    assert 'ctid' not in statements[0]
    assert 'target.news_id = normalized.news_id' in statements[0]
    assert 'target.create_time = normalized.create_time' in statements[0]
