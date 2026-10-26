import importlib
from pathlib import Path

import tomllib

import app.entrypoints.task_worker
import app.infrastructure.models.audit
import app.infrastructure.models.jobs
import app.intelligence.models.ai_models
import app.intelligence.models.pipeline_models
import app.system.models.config
import app.system.models.dictionary
import app.system.models.menu
import app.system.models.role
import app.system.models.user  # noqa: F401
from app.entrypoints.routes import CONTROLLER_MODULES, _routers_from_module
from app.intelligence.api import pipeline_controller
from config.database import Base

LEGACY_PACKAGE_NAMES = (
    'module_admin',
    'module_ai',
    'module_manuscript',
    'module_pipeline',
    'module_task',
    'module_generator',
)


def test_app_package_is_the_canonical_api_entrypoint() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    canonical_files = (
        app_root / '__init__.py',
        app_root / 'entrypoints' / 'api.py',
        app_root / 'entrypoints' / 'routes.py',
        app_root / 'bootstrap.py',
        app_root / 'health' / 'api' / 'controller.py',
        app_root / 'system' / 'api' / 'dependencies.py',
        app_root / 'infrastructure' / 'services' / 'file_storage.py',
        app_root / 'infrastructure' / 'services' / 'file_transfer.py',
        app_root / 'infrastructure' / 'services' / 'formatting.py',
        app_root / 'infrastructure' / 'services' / 'datetime_formatting.py',
        app_root / 'infrastructure' / 'services' / 'string_support.py',
        app_root / 'infrastructure' / 'services' / 'logging_support.py',
        app_root / 'infrastructure' / 'services' / 'serialization.py',
        app_root / 'infrastructure' / 'services' / 'startup_banner.py',
        app_root / 'infrastructure' / 'services' / 'file_upload.py',
        app_root / 'infrastructure' / 'services' / 'cron_expression.py',
        app_root / 'infrastructure' / 'services' / 'runtime.py',
        app_root / 'infrastructure' / 'services' / 'transport_crypto_core.py',
        app_root / 'infrastructure' / 'services' / 'secret_crypto.py',
        app_root / 'infrastructure' / 'services' / 'excel_export.py',
        app_root / 'infrastructure' / 'services' / 'pagination.py',
        app_root / 'system' / 'services' / 'files.py',
        app_root / 'system' / 'services' / 'notification.py',
        app_root / 'system' / 'services' / 'passwords.py',
        app_root / 'intelligence' / 'models' / 'pipeline_models.py',
        app_root / 'intelligence' / 'models' / 'collection.py',
        app_root / 'intelligence' / 'models' / 'configuration.py',
        app_root / 'intelligence' / 'models' / 'content.py',
        app_root / 'intelligence' / 'models' / 'ai_models.py',
        app_root / 'research' / 'services' / 'model_generation.py',
        app_root / 'intelligence' / 'services' / 'application.py',
        app_root / 'intelligence' / 'api' / 'controller.py',
        app_root / 'intelligence' / 'api' / 'pipeline_controller.py',
        app_root / 'intelligence' / 'api' / 'ai_model_controller.py',
        app_root / 'intelligence' / 'services' / 'categories.py',
        app_root / 'intelligence' / 'repositories' / 'content_repository.py',
        app_root / 'intelligence' / 'tasks' / 'collection_scheduler.py',
        app_root / 'library' / 'api' / 'controller.py',
        app_root / 'library' / 'models' / 'materials.py',
        app_root / 'library' / 'services' / 'materials.py',
        app_root / 'library' / 'tasks' / 'material_parse_scheduler.py',
        app_root / 'research' / 'api' / 'controller.py',
        app_root / 'research' / 'models' / 'research_models.py',
        app_root / 'research' / 'services' / 'application.py',
        app_root / 'research' / 'services' / 'jobs.py',
        app_root / 'research' / 'services' / 'evidence.py',
        app_root / 'research' / 'services' / 'execution.py',
    )
    assert all(path.is_file() for path in canonical_files)
    assert not (backend_root / 'app.py').exists()
    assert not (app_root / 'intelligence' / 'services' / 'api.py').exists()
    assert not (app_root / 'research' / 'services' / 'api.py').exists()


def test_application_orchestration_is_not_misnamed_as_http_api() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    active_roots = (app_root / 'intelligence', app_root / 'research')
    for root in active_roots:
        for path in root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert '.services.api' not in source, path
            assert 'IntelligenceApiService' not in source, path
            assert 'ResearchApiService' not in source, path


def test_all_app_packages_are_included_in_the_wheel_package_manifest() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    pyproject = tomllib.loads((backend_root / 'pyproject.toml').read_text(encoding='utf-8'))
    declared = set(pyproject['tool']['setuptools']['packages'])
    actual = {'.'.join(path.parent.relative_to(app_root.parent).parts) for path in app_root.rglob('__init__.py')}

    assert actual <= declared
    assert not any(package.startswith('module_') for package in declared)


def test_legacy_module_directories_and_imports_are_removed() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    for package_name in LEGACY_PACKAGE_NAMES:
        assert not (backend_root / package_name).exists(), package_name

    active_roots = (
        backend_root / 'src' / 'app',
        backend_root / 'cli',
        backend_root / 'common',
        backend_root / 'config',
        backend_root / 'scripts',
        backend_root / 'server.py',
    )
    for root in active_roots:
        paths = [root] if root.is_file() else root.rglob('*.py')
        for path in paths:
            source = path.read_text(encoding='utf-8')
            assert not any(f'{package_name}.' in source for package_name in LEGACY_PACKAGE_NAMES), path


def test_global_utils_package_is_retired() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    utils_root = backend_root / 'utils'
    pyproject = tomllib.loads((backend_root / 'pyproject.toml').read_text(encoding='utf-8'))

    assert not any(utils_root.glob('*.py'))
    assert 'utils' not in set(pyproject['tool']['setuptools']['packages'])

    active_roots = (
        backend_root / 'src' / 'app',
        backend_root / 'cli',
        backend_root / 'common',
        backend_root / 'config',
        backend_root / 'scripts',
        backend_root / 'server.py',
    )
    for root in active_roots:
        paths = [root] if root.is_file() else root.rglob('*.py')
        for path in paths:
            source = path.read_text(encoding='utf-8')
            assert 'from utils.' not in source
            assert 'import utils.' not in source


def test_retired_processing_preserves_only_packaged_resources_and_namespace_markers() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    processing_root = backend_root / 'src' / 'app' / 'intelligence' / 'processing'
    pyproject = tomllib.loads((backend_root / 'pyproject.toml').read_text(encoding='utf-8'))
    package_data = pyproject['tool']['setuptools']['package-data']

    assert not (processing_root / 'main.py').exists()
    assert all(path.name == '__init__.py' for path in processing_root.rglob('*.py'))
    assert (processing_root / 'supported_text' / 'politics_stopwords.txt').is_file()
    assert (processing_root / 'email_support' / 'templates' / 'alert_email.html').is_file()
    assert not (processing_root / 'utils').exists()
    assert all('news_processor' not in path.read_text(encoding='utf-8') for path in processing_root.rglob('*.py'))
    assert 'supported_text/*.txt' in package_data['app.intelligence.processing']
    assert 'email_support/templates/*' in package_data['app.intelligence.processing']


def test_business_model_gateway_replaces_personal_chat_provider_factory() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'research' / 'services' / 'model_generation.py').is_file()
    assert not (app_root / 'intelligence' / 'services' / 'model_provider.py').exists()
    assert not (backend_root / 'utils' / 'ai_util.py').exists()


def test_scheduler_expression_validation_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'cron_expression.py').is_file()
    assert not (backend_root / 'utils' / 'cron_util.py').exists()


def test_runtime_bootstrap_helpers_are_not_global_server_utilities() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'runtime.py').is_file()
    assert not (backend_root / 'utils' / 'server_util.py').exists()


def test_file_upload_support_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'file_upload.py').is_file()
    assert not (backend_root / 'utils' / 'upload_util.py').exists()


def test_transport_crypto_core_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'transport_crypto_core.py').is_file()
    assert not (backend_root / 'utils' / 'transport_crypto_util.py').exists()


def test_secret_crypto_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'secret_crypto.py').is_file()
    assert not (backend_root / 'utils' / 'crypto_util.py').exists()


def test_excel_export_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'excel_export.py').is_file()
    assert not (backend_root / 'utils' / 'excel_util.py').exists()


def test_pagination_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'pagination.py').is_file()
    assert not (backend_root / 'utils' / 'page_util.py').exists()


def test_shared_file_streaming_and_formatting_are_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'file_transfer.py').is_file()
    assert (app_root / 'infrastructure' / 'services' / 'formatting.py').is_file()
    assert not (backend_root / 'utils' / 'common_util.py').exists()


def test_shared_serialization_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'serialization.py').is_file()
    assert (app_root / 'infrastructure' / 'services' / 'startup_banner.py').is_file()
    assert not (backend_root / 'utils' / 'common_util.py').exists()


def test_sms_code_notification_is_owned_by_system_services() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'system' / 'services' / 'notification.py').is_file()
    assert not (backend_root / 'utils' / 'message_util.py').exists()


def test_password_hashing_is_owned_by_system_services() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'system' / 'services' / 'passwords.py').is_file()
    assert not (backend_root / 'utils' / 'pwd_util.py').exists()


def test_datetime_formatting_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'datetime_formatting.py').is_file()
    assert not (backend_root / 'utils' / 'time_format_util.py').exists()


def test_string_support_is_owned_by_infrastructure() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'string_support.py').is_file()
    assert not (backend_root / 'utils' / 'string_util.py').exists()


def test_http_cross_cutting_support_is_not_global_utils() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    common_root = backend_root / 'common'
    expected_files = (
        common_root / 'http' / '__init__.py',
        common_root / 'http' / 'request_support.py',
        common_root / 'http' / 'response_headers.py',
        common_root / 'http' / 'client_ip.py',
        common_root / 'http' / 'dependencies.py',
    )

    assert all(path.is_file() for path in expected_files)
    for filename in (
        'api_annotation_util.py',
        'api_response_header_util.py',
        'client_ip_util.py',
        'dependency_util.py',
    ):
        assert not (backend_root / 'utils' / filename).exists()


def test_alembic_model_discovery_is_owned_by_configuration() -> None:
    backend_root = Path(__file__).resolve().parents[2]

    assert (backend_root / 'config' / 'model_discovery.py').is_file()
    assert not (backend_root / 'utils' / 'import_util.py').exists()


def test_logging_and_response_adapters_are_not_global_utils() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (app_root / 'infrastructure' / 'services' / 'logging_support.py').is_file()
    assert (backend_root / 'common' / 'http' / 'responses.py').is_file()
    assert not (backend_root / 'utils' / 'log_util.py').exists()
    assert not (backend_root / 'utils' / 'response_util.py').exists()


def test_task_worker_registers_system_foreign_key_metadata() -> None:
    assert {'sys_job', 'sys_user', 'sys_role', 'sys_menu'} <= set(Base.metadata.tables)
    assert not {'scheduled_jobs', 'users', 'roles', 'menus'} & set(Base.metadata.tables)
    # Resolve every registered FK, including canonical composite references.
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.key in Base.metadata.tables


def test_business_layers_do_not_depend_on_legacy_facades_or_http_adapters() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    business_roots = tuple(app_root / name for name in ('intelligence', 'library', 'research'))
    forbidden_imports = ('module_admin.', 'module_ai.', 'module_pipeline.')

    for business_root in business_roots:
        for path in business_root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert not any(forbidden_import in source for forbidden_import in forbidden_imports), path


def test_business_services_and_repositories_do_not_depend_on_http_frameworks() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    business_roots = tuple(
        app_root / name / layer
        for name in ('intelligence', 'library', 'research')
        for layer in ('services', 'repositories')
    )

    for root in business_roots:
        if not root.exists():
            continue
        for path in root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert 'from fastapi' not in source, path
            assert 'import fastapi' not in source, path
            assert 'from app.' not in source or '.api.' not in source, path


def test_cache_and_online_services_receive_redis_as_a_runtime_dependency() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_sources = (
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'cache.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'online.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'jobs.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'job_logs.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'log.py',
        backend_root / 'src' / 'app' / 'system' / 'services' / 'configuration.py',
        backend_root / 'src' / 'app' / 'system' / 'services' / 'dictionary.py',
    )

    for path in service_sources:
        source = path.read_text(encoding='utf-8')
        assert 'from fastapi' not in source
        assert 'request.app.state' not in source
        assert 'aioredis.Redis' in source


def test_user_import_service_receives_redis_as_a_runtime_dependency() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / 'src' / 'app' / 'system' / 'services' / 'users.py').read_text(encoding='utf-8')

    assert 'from fastapi import Request' not in source
    assert 'from fastapi' not in source
    assert 'request.app.state' not in source
    assert 'aioredis.Redis' in source


def test_login_http_dependencies_are_owned_by_the_api_layer() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_source = (backend_root / 'src' / 'app' / 'system' / 'services' / 'authentication.py').read_text(
        encoding='utf-8'
    )
    dependency_source = (backend_root / 'src' / 'app' / 'system' / 'api' / 'login_dependencies.py').read_text(
        encoding='utf-8'
    )

    assert 'from fastapi' not in service_source
    assert 'OAuth2Password' not in service_source
    assert 'from fastapi' in dependency_source
    assert 'LoginFormDependency' in dependency_source
    assert 'OAuth2PasswordBearer' not in dependency_source
    assert 'common.http.security' in dependency_source


def test_oauth2_scheme_has_one_common_http_owner() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    security_source = (backend_root / 'common' / 'http' / 'security.py').read_text(encoding='utf-8')
    pre_auth_source = (backend_root / 'common' / 'aspect' / 'pre_auth.py').read_text(encoding='utf-8')

    assert security_source.count('OAuth2PasswordBearer(') == 1
    assert "tokenUrl='/login'" in security_source
    assert 'common.http.security import oauth2_scheme' in pre_auth_source


def test_collection_service_delegates_public_source_networking_to_integrations() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_source = (backend_root / 'src' / 'app' / 'intelligence' / 'services' / 'collection.py').read_text(
        encoding='utf-8'
    )
    integration_path = backend_root / 'src' / 'app' / 'intelligence' / 'integrations' / 'public_sources.py'
    integration_source = integration_path.read_text(encoding='utf-8')

    assert 'urllib.request' not in service_source
    bridge_source = (integration_path.parent / 'public_source_bridge.py').read_text(encoding='utf-8')
    assert 'register_builtin_adapters' in service_source
    assert 'httpx' not in service_source
    assert 'httpx.AsyncClient' in bridge_source
    assert 'app.intelligence.integrations.public_sources' in bridge_source
    assert 'urlopen' in integration_source


def test_collection_persistence_owns_record_storage_rules() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_source = (backend_root / 'src' / 'app' / 'intelligence' / 'services' / 'collection.py').read_text(
        encoding='utf-8'
    )
    persistence_source = (
        backend_root / 'src' / 'app' / 'intelligence' / 'services' / 'collection_persistence.py'
    ).read_text(encoding='utf-8')

    assert 'CollectionPersistenceService.save_batch' in service_source
    assert 'class CollectionPersistenceService' in persistence_source
    assert 'async def save_record' in persistence_source
    assert 'PipelineDataProcessingService' not in persistence_source
    assert 'PipelineArticle' in persistence_source
    assert 'PipelinePaper' in persistence_source
    assert 'category_id=category_id' in persistence_source


def test_retired_governance_has_no_registered_model_or_service() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    intelligence = backend_root / 'src/app/intelligence'
    for name in ('governance', 'governance_issues', 'governance_duplicates', 'reviews'):
        assert not (intelligence / 'services' / f'{name}.py').exists()
    assert not (intelligence / 'models/governance.py').exists()
    assert not {'quality_issues', 'quality_issue_events', 'content_review_events'} & set(Base.metadata.tables)


def test_all_controller_modules_import_without_registering_retired_tables() -> None:
    for module_name in CONTROLLER_MODULES:
        module = importlib.import_module(module_name)
        assert _routers_from_module(module), module_name
    retired = {
        'duplicate_groups',
        'duplicate_members',
        'duplicate_group_events',
        'model_routes',
        'model_route_usage',
        'prompt_versions',
    }
    assert not retired & set(Base.metadata.tables)
    assert not any(table.schema == 'news' for table in Base.metadata.tables.values())
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.key in Base.metadata.tables


def test_authentication_service_receives_runtime_dependencies_explicitly() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / 'src' / 'app' / 'system' / 'services' / 'authentication.py').read_text(encoding='utf-8')

    assert 'from fastapi import Request' not in source
    assert 'from fastapi' not in source
    assert 'request.app.state' not in source
    assert 'common.http.context' not in source
    assert 'RequestContext' not in source
    assert 'aioredis.Redis' in source


def test_file_transfer_services_receive_base_url_instead_of_request() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_sources = (
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_storage.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_transfer.py',
    )

    for path in service_sources:
        source = path.read_text(encoding='utf-8')
        assert 'from fastapi import Request' not in source
        assert 'request.app.state' not in source
        assert 'base_url' in source


def test_file_services_depend_on_upload_port_not_fastapi_upload_file() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    service_sources = (
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_upload.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_storage.py',
        backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_transfer.py',
        backend_root / 'src' / 'app' / 'system' / 'services' / 'users.py',
    )

    for path in service_sources:
        source = path.read_text(encoding='utf-8')
        assert 'from fastapi import UploadFile' not in source
        assert 'UploadFilePort' in source


def test_file_transfer_service_depends_on_background_task_port() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'file_transfer.py').read_text(
        encoding='utf-8'
    )

    assert 'from fastapi import BackgroundTasks' not in source
    assert 'BackgroundTasksPort' in source


def test_transport_crypto_service_receives_redis_instead_of_app() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'transport_crypto.py').read_text(
        encoding='utf-8'
    )

    assert 'from fastapi import Request' not in source
    assert 'request.app.state' not in source
    assert 'from fastapi import' not in source
    assert 'aioredis.Redis' in source


def test_transport_crypto_core_receives_replay_dependencies_explicitly() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / 'src' / 'app' / 'infrastructure' / 'services' / 'transport_crypto_core.py').read_text(
        encoding='utf-8'
    )

    assert 'from fastapi import Request' not in source
    assert 'request.app.state' not in source
    assert 'from fastapi import' not in source
    assert 'aioredis.Redis' in source
    assert 'fail_closed: bool' in source


def test_research_and_library_own_their_models() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    material_source = (app_root / 'library' / 'models' / 'materials.py').read_text(encoding='utf-8')
    research_source = (app_root / 'research' / 'models' / 'research_models.py').read_text(encoding='utf-8')
    pipeline_source = (app_root / 'intelligence' / 'models' / 'pipeline_models.py').read_text(encoding='utf-8')

    assert 'class PipelineMaterial' in material_source
    assert 'class PipelineMaterial' not in pipeline_source
    for class_name in ('PipelineWorkspaceItem', 'PipelineResearchJob', 'PipelineReport', 'PipelineReportVersion'):
        assert f'class {class_name}' in research_source
        assert f'class {class_name}' not in pipeline_source


def test_application_routes_are_explicit_and_canonical() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    route_source = (backend_root / 'src' / 'app' / 'entrypoints' / 'routes.py').read_text(encoding='utf-8')
    routing_path = backend_root / 'common' / 'http' / 'routing.py'
    routing_source = routing_path.read_text(encoding='utf-8')

    assert CONTROLLER_MODULES
    assert all(module_name.startswith('app.') for module_name in CONTROLLER_MODULES)
    assert not any(f'{package_name}.' in route_source for package_name in LEGACY_PACKAGE_NAMES)
    assert "'app.intelligence.api.pipeline_controller'" in route_source
    assert "'app.system.api.login_controller'" in route_source
    assert routing_path.is_file()
    assert not (backend_root / 'common' / 'router.py').exists()
    assert 'RouterRegister' not in routing_source
    assert 'auto_register_routers' not in routing_source
    assert 'glob.glob' not in routing_source


def test_http_contracts_are_owned_by_the_common_http_package() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    http_root = backend_root / 'common' / 'http'

    assert (http_root / 'schemas.py').is_file()
    assert (http_root / 'responses.py').is_file()
    assert (http_root / 'context.py').is_file()
    assert (http_root / 'dependencies.py').is_file()
    assert not (backend_root / 'common' / 'vo.py').exists()
    assert not (backend_root / 'common' / 'context.py').exists()
    assert not (backend_root / 'common' / 'dependencies.py').exists()

    active_roots = (
        backend_root / 'src' / 'app',
        backend_root / 'cli',
        backend_root / 'common',
        backend_root / 'config',
        backend_root / 'tests',
    )
    legacy_response_module = 'common' + '.vo'
    legacy_context_module = 'common' + '.context'
    legacy_dependencies_module = 'common' + '.dependencies'
    for root in active_roots:
        for path in root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert legacy_response_module not in source, path
            assert legacy_context_module not in source, path
            assert legacy_dependencies_module not in source, path


def test_module_schemas_are_not_nested_under_http_api_packages() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'
    schema_roots = (
        app_root / 'system' / 'schemas',
        app_root / 'infrastructure' / 'schemas',
        app_root / 'intelligence' / 'schemas',
        app_root / 'research' / 'schemas',
    )

    assert all(path.is_dir() for path in schema_roots)
    assert not (app_root / 'system' / 'api' / 'schemas').exists()
    assert not (app_root / 'infrastructure' / 'api' / 'schemas').exists()
    assert not (app_root / 'intelligence' / 'api' / 'schemas.py').exists()
    assert not (app_root / 'intelligence' / 'api' / 'ai_model_schemas.py').exists()
    assert not (app_root / 'intelligence' / 'api' / 'ai_chat_schemas.py').exists()
    assert not (app_root / 'research' / 'api' / 'manuscript_schemas.py').exists()

    for path in app_root.rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert '.api.schemas' not in source, path
        assert '.api.ai_model_schemas' not in source, path
        assert '.api.ai_chat_schemas' not in source, path
        assert '.api.manuscript_schemas' not in source, path


def test_shared_constants_have_explicit_owners() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / 'src' / 'app'

    assert (backend_root / 'common' / 'constants.py').is_file()
    assert (backend_root / 'common' / 'http' / 'status.py').is_file()
    assert (backend_root / 'common' / 'http' / 'contracts.py').is_file()
    assert (app_root / 'system' / 'constants.py').is_file()
    assert not (backend_root / 'common' / 'constant.py').exists()

    legacy_constant_import = 'from common' + '.constant import'
    legacy_constant_dynamic_import = "import_module('common" + ".constant')"
    active_roots = (app_root, backend_root / 'cli', backend_root / 'common', backend_root / 'config')
    for root in active_roots:
        for path in root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert legacy_constant_import not in source, path
            assert legacy_constant_dynamic_import not in source, path


def test_shared_enums_have_explicit_owners() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    enum_root = backend_root / 'common' / 'enums'

    assert (enum_root / '__init__.py').is_file()
    assert (enum_root / 'http.py').is_file()
    assert (enum_root / 'audit.py').is_file()
    assert (enum_root / 'cache.py').is_file()
    assert not (backend_root / 'common' / 'enums.py').exists()

    legacy_enum_import = 'from common' + '.enums import'
    legacy_enum_dynamic_import = "load_runtime_module('common" + ".enums')"
    active_roots = (backend_root / 'src' / 'app', backend_root / 'cli', backend_root / 'common')
    for root in active_roots:
        for path in root.rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            assert legacy_enum_import not in source, path
            assert legacy_enum_dynamic_import not in source, path


def test_cli_cross_cutting_support_has_explicit_owners() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    cli_root = backend_root / 'cli'

    assert (cli_root / 'output.py').is_file()
    assert (cli_root / 'runtime' / 'nested_cli.py').is_file()
    assert not (cli_root / 'utils.py').exists()

    legacy_cli_utils_module = 'cli' + '.utils'
    for path in cli_root.rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert legacy_cli_utils_module not in source, path


def test_aggregated_pipeline_module_registers_only_its_own_router() -> None:
    routers = _routers_from_module(pipeline_controller)
    assert [(name, router) for name, router in routers] == [
        ('pipeline_controller', pipeline_controller.pipeline_controller)
    ]


def test_retired_code_generator_and_scheduler_demo_have_no_runtime_entrypoints() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    pyproject_source = (backend_root / 'pyproject.toml').read_text(encoding='utf-8')
    scheduler_source = (backend_root / 'config' / 'get_scheduler.py').read_text(encoding='utf-8')
    constant_source = (backend_root / 'common' / 'constants.py').read_text(encoding='utf-8')

    assert 'tooling.generator' not in pyproject_source
    assert 'module_task' not in pyproject_source
    assert 'import module_task' not in scheduler_source
    assert "JOB_WHITE_LIST = ['app.']" in constant_source
    for filename in ('ruoyi-fastapi.sql', 'ruoyi-fastapi-pg.sql'):
        sql_source = (backend_root / 'sql' / filename).read_text(encoding='utf-8')
        assert 'module_task.scheduler_test' not in sql_source


def test_app_bootstrap_owns_the_application_factory() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    bootstrap_source = (backend_root / 'src' / 'app' / 'bootstrap.py').read_text(encoding='utf-8')
    server_source = (backend_root / 'server.py').read_text(encoding='utf-8')

    assert 'def create_app' in bootstrap_source
    assert 'from app.bootstrap import' in server_source
