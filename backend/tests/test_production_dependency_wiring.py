"""Cross-process invariants: workers must use the API's database, keys and quota cache."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_api_worker_and_migrator_share_the_explicit_database_and_credentials():
    services = yaml.safe_load((ROOT / 'docker-compose.pg.yml').read_text())['services']
    api = services['ruoyi-backend-pg']['environment']
    worker = services['pipesight-task-worker']['environment']
    migration = services['pipesight-db-migrate']['environment']
    for key in ('DB_HOST', 'DB_PORT', 'DB_USERNAME', 'DB_PASSWORD', 'DB_DATABASE'):
        assert api[key] == worker[key] == migration[key]
    assert ':?' in api['DB_HOST']  # No implicit production target.
    assert api['JWT_SECRET_KEY'] == worker['JWT_SECRET_KEY']
    for key in ('REDIS_HOST', 'REDIS_PORT', 'REDIS_DATABASE'):
        assert api[key] == worker[key]
    assert worker['REDIS_HOST'] in services
    for name in ('ruoyi-backend-pg', 'pipesight-task-worker'):
        process = services[name]
        assert process['depends_on'][worker['REDIS_HOST']]['condition'] == 'service_healthy'
        assert process['depends_on'][worker['FILE_SCAN_HOST']]['condition'] == 'service_healthy'
        assert process['depends_on']['pipesight-db-migrate']['condition'] == 'service_completed_successfully'
        assert any(str(mount).endswith(':/app/fonts:ro') for mount in process['volumes'])


def test_scanner_is_private_and_worker_health_does_not_depend_on_api_readiness():
    services = yaml.safe_load((ROOT / 'docker-compose.pg.yml').read_text())['services']
    worker = services['pipesight-task-worker']
    scanner = services[worker['environment']['FILE_SCAN_HOST']]
    assert not scanner.get('ports')
    assert not services['ruoyi-backend-pg'].get('ports')
    assert worker['healthcheck']['test'] == ['CMD', 'pipesight-worker-health']
    assert services['pipesight-db-migrate']['command'] == ['pipesight-safe-migrate']
    assert all(
        process.get('restart') for process in services.values() if process is not services['pipesight-db-migrate']
    )
