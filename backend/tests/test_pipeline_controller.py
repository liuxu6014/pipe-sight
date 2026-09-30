from module_pipeline.controller.pipeline_controller import pipeline_controller


def test_pipeline_controller_exposes_mvp_action_routes() -> None:
    routes = {(route.path, tuple(sorted(route.methods))) for route in pipeline_controller.routes}

    assert ('/pipeline/tasks/{task_id}/run', ('POST',)) in routes
    assert ('/pipeline/tasks/runs/{run_id}/handoff', ('POST',)) in routes
    assert ('/pipeline/tasks/runs/{run_id}/handoff/sync', ('POST',)) in routes
    assert ('/pipeline/reports/{report_id}/export', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents', ('POST',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}', ('DELETE',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}/retry', ('POST',)) in routes
    assert ('/pipeline/knowledge/ask', ('POST',)) in routes
    assert ('/pipeline/workspace', ('GET',)) in routes
    assert ('/pipeline/workspace/items', ('POST',)) in routes
    assert ('/pipeline/research/jobs', ('POST',)) in routes
    assert ('/pipeline/research/jobs/{job_id}', ('GET',)) in routes
    assert ('/pipeline/research/jobs/{job_id}/cancel', ('POST',)) in routes
    assert ('/pipeline/research/jobs/{job_id}/retry', ('POST',)) in routes
    assert ('/pipeline/research/reports/{report_id}', ('PUT',)) in routes
    assert ('/pipeline/research/reports/{report_id}/diagram', ('GET',)) in routes
    assert ('/pipeline/research/reports/{report_id}/diagram', ('PUT',)) in routes
    assert ('/pipeline/research/reports/{report_id}/versions', ('GET',)) in routes
    assert ('/pipeline/research/reports/{report_id}/versions/{version_no}', ('GET',)) in routes
    assert ('/pipeline/research/reports/{report_id}/versions/{version_no}/restore', ('POST',)) in routes
