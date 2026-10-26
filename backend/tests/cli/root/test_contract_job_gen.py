import subprocess
from collections.abc import Callable

from cli.exit_codes import DATABASE_ERROR, RUNTIME_ERROR, SUCCESS

MISSING_JOB_ID = 999999999


def test_job_detail_json_output_has_stable_contract(
    run_cli_command: Callable[..., subprocess.CompletedProcess[str]],
    parse_json_stdout: Callable[[subprocess.CompletedProcess[str]], dict],
) -> None:
    list_completed = run_cli_command('job', 'list', '--env=dev', '--output=json')
    list_payload = parse_json_stdout(list_completed)
    job_id = MISSING_JOB_ID
    if list_payload.get('ok') and isinstance(list_payload.get('items'), list) and list_payload['items']:
        first_job = list_payload['items'][0]
        if isinstance(first_job, dict) and isinstance(first_job.get('jobId'), int):
            job_id = first_job['jobId']

    completed = run_cli_command('job', 'detail', str(job_id), '--env=dev', '--output=json')
    payload = parse_json_stdout(completed)

    assert completed.returncode in {SUCCESS, DATABASE_ERROR, RUNTIME_ERROR}
    assert isinstance(payload['ok'], bool)
    if 'error' in payload:
        assert isinstance(payload['message'], str)
        assert isinstance(payload['error'], str)
        return

    if payload['ok'] is False:
        assert set(payload) == {'ok', 'message', 'jobId'}
        assert payload['jobId'] == job_id
        return

    assert set(payload) == {'ok', 'job'}
    assert isinstance(payload['job'], dict)
    assert payload['job']['jobId'] == job_id
    assert isinstance(payload['job'].get('jobName'), str)
    assert isinstance(payload['job'].get('invokeTarget'), str)


def test_job_logs_json_output_has_stable_contract(
    run_cli_command: Callable[..., subprocess.CompletedProcess[str]],
    parse_json_stdout: Callable[[subprocess.CompletedProcess[str]], dict],
) -> None:
    completed = run_cli_command('job', 'logs', '--env=dev', '--output=json')
    payload = parse_json_stdout(completed)

    assert completed.returncode in {SUCCESS, DATABASE_ERROR}
    assert isinstance(payload['ok'], bool)
    if 'error' in payload:
        assert isinstance(payload['message'], str)
        assert isinstance(payload['error'], str)
        return

    assert set(payload) == {'ok', 'filters', 'count', 'items'}
    assert isinstance(payload['filters'], dict)
    assert isinstance(payload['count'], int)
    assert isinstance(payload['items'], list)
    if payload['items']:
        first_item = payload['items'][0]
        assert isinstance(first_item, dict)
        assert isinstance(first_item.get('jobLogId'), int)
        assert isinstance(first_item.get('jobName'), str | None)
        assert isinstance(first_item.get('jobMessage'), str | None)
