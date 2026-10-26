"""Guard the approved retirement without loading old models or ignoring tests."""

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'src/app'
PROCESSING = APP / 'intelligence/processing'
PRESERVED_TEXT_COUNT = 10
RETIRED_MODULES = (
    'app.intelligence.services.governance',
    'app.intelligence.services.governance_duplicates',
    'app.intelligence.services.governance_issues',
    'app.intelligence.services.reviews',
    'app.intelligence.services.handoff',
    'app.intelligence.services.model_routes',
    'app.intelligence.services.model_audits',
    'app.intelligence.services.prompts',
    'app.intelligence.services.model_execution',
    'app.intelligence.tasks.handoff_scheduler',
    'app.intelligence.models.governance',
    'app.intelligence.api.internal_controller',
)
RETIRED_TABLES = (
    'quality_issues',
    'quality_issue_events',
    'duplicate_groups',
    'duplicate_members',
    'duplicate_group_events',
    'content_review_events',
    'model_routes',
    'model_route_usage',
    'prompt_versions',
    'news.articles',
    'news.data_sources',
    'news.domains',
    'news.topics',
    'news.domain_topic_rules',
    'news.prompt_versions',
    'news.prompt_usages',
    'news.embeddings',
)


@pytest.mark.parametrize('module', RETIRED_MODULES)
def test_retired_module_source_is_removed(module: str) -> None:
    assert not (ROOT / 'src' / (module.replace('.', '/') + '.py')).exists()


def test_processing_contains_no_runtime_code() -> None:
    for path in PROCESSING.rglob('*.py'):
        assert path.name == '__init__.py', path
        # Even package initializers must have no imports, registration or execution.
        tree = ast.parse(path.read_text(encoding='utf-8'))
        assert all(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) for node in tree.body), path


def test_resources_are_preserved_byte_for_byte() -> None:
    common_digest = '89b69d796b58d2bd8791bad2b92127300b710a88679b2ff65c913c9ae883c01f'
    files = list((PROCESSING / 'supported_text').glob('*.txt'))
    assert len(files) == PRESERVED_TEXT_COUNT
    for path in files:
        expected = (
            '061be1be22e7de4fcf94e6a5dbfe89df65ce95846c81754daa8b58c56b5bde25'
            if path.name == 'security_stopwords.txt'
            else common_digest
        )
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    template = PROCESSING / 'email_support/templates/alert_email.html'
    assert (
        hashlib.sha256(template.read_bytes()).hexdigest()
        == 'f8ee5a4b10f7ef6c2da617cfd18ff0311af0cadc82ab322cf36ca62fe5e2e204'
    )


def test_active_imports_do_not_reference_retired_modules() -> None:
    errors = []
    for root in (APP, ROOT / 'cli'):
        for path in root.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ''
                    names = [base, *(f'{base}.{alias.name}' for alias in node.names)]
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    # Also cover dynamic import_module registry strings.
                    names = [node.value]
                else:
                    continue
                errors.extend(
                    f'{path.relative_to(ROOT)}:{node.lineno}: {name}'
                    for name in names
                    if name in RETIRED_MODULES or name.startswith('app.intelligence.processing.')
                )
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('entrypoint', ['api', 'worker'])
def test_entrypoints_import_offline_without_legacy_registration(entrypoint: str) -> None:
    # A fresh process catches transitive and lazy imports; no app startup/lifespan.
    source = f"""
import socket
def forbidden(*args, **kwargs):
    raise AssertionError('External connections are forbidden')
socket.socket.connect = forbidden
socket.create_connection = forbidden
import importlib.abc
import sys
class NoLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {RETIRED_MODULES!r} or fullname.startswith('app.intelligence.processing.'):
            raise AssertionError('Retired module imported: ' + fullname)
sys.meta_path.insert(0, NoLegacy())
if {entrypoint!r} == 'worker':
    import app.entrypoints.task_worker
import config.get_scheduler
from app.entrypoints.routes import CONTROLLER_MODULES, register_application_routers
from fastapi import FastAPI
from config.database import Base
app = FastAPI()
register_application_routers(app)
assert not any(path.startswith('/pipeline/internal') or '/model-routes' in path for path in (route.path for route in app.routes))
assert not set({RETIRED_TABLES!r}) & set(Base.metadata.tables)
assert not any(table.schema == 'news' for table in Base.metadata.tables.values())
from cli.main import CLI_MAIN_RUNNER
from typer.testing import CliRunner
result = CliRunner().invoke(CLI_MAIN_RUNNER.build_cli(), ['--help'])
assert result.exit_code == 0, result.output
print('API/worker/scheduler/CLI loaded; retired tables absent; no connections')
"""
    result = subprocess.run(
        [sys.executable, '-c', source], cwd=ROOT, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_still_uses_direct_canonical_classification() -> None:
    # Ownership stays with the collection agent; this guard detects regressions.
    source = (APP / 'intelligence/services/collection.py').read_text(encoding='utf-8')
    assert 'CategoryService.classify' in source
    category_source = (APP / 'intelligence/services/categories.py').read_text(encoding='utf-8')
    assert 'ModelGateway' in category_source
    assert 'PipelineCategory' in category_source
    assert 'model_routes' not in category_source
    assert 'prompt_versions' not in category_source
