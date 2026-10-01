from module_pipeline.controller.pipeline_controller import pipeline_controller


def test_pipeline_controller_exposes_mvp_action_routes() -> None:
    routes = {(route.path, tuple(sorted(route.methods))) for route in pipeline_controller.routes}

    assert ('/pipeline/tasks/{task_id}/run', ('POST',)) in routes
    assert ('/pipeline/sources', ('POST',)) in routes
    assert ('/pipeline/sources/{source_id}', ('PUT',)) in routes
    assert ('/pipeline/sources/{source_id}', ('DELETE',)) in routes
    assert ('/pipeline/templates', ('GET',)) in routes
    assert ('/pipeline/templates', ('POST',)) in routes
    assert ('/pipeline/templates/{template_key}', ('PUT',)) in routes
    assert ('/pipeline/templates/{template_key}', ('DELETE',)) in routes
    assert ('/pipeline/templates/{template_key}/publish', ('POST',)) in routes
    assert ('/pipeline/prompts', ('GET',)) in routes
    assert ('/pipeline/prompts', ('POST',)) in routes
    assert ('/pipeline/prompts/{prompt_key}/test', ('POST',)) in routes
    assert ('/pipeline/prompts/{prompt_key}/publish', ('POST',)) in routes
    assert ('/pipeline/tasks/runs/{run_id}/handoff', ('POST',)) in routes
    assert ('/pipeline/tasks/runs/{run_id}/handoff/sync', ('POST',)) in routes
    assert ('/pipeline/reports/{report_id}/export', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents', ('POST',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}/download', ('GET',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}', ('DELETE',)) in routes
    assert ('/pipeline/knowledge/documents/{material_id}/retry', ('POST',)) in routes
    assert ('/pipeline/knowledge/ask', ('POST',)) not in routes
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


def test_pipeline_management_routes_require_explicit_interface_permissions() -> None:
    protected = {
        (route.path, tuple(sorted(route.methods))): route
        for route in pipeline_controller.routes
        if (route.path, tuple(sorted(route.methods))) in {
            ('/pipeline/sources', ('GET',)),
            ('/pipeline/tasks', ('GET',)),
            ('/pipeline/tasks/{task_id}/run', ('POST',)),
        }
    }

    assert all(route.dependencies for route in protected.values())
    assert any(getattr(dependency.dependency, 'perm', None) == 'pipeline:source:list' for dependency in protected[('/pipeline/sources', ('GET',))].dependencies)
    assert any(getattr(dependency.dependency, 'perm', None) == 'pipeline:task:list' for dependency in protected[('/pipeline/tasks', ('GET',))].dependencies)

    prompt_routes = {
        (route.path, tuple(sorted(route.methods))): route
        for route in pipeline_controller.routes
        if route.path.startswith('/pipeline/prompts')
    }
    assert all(route.dependencies for route in prompt_routes.values())
    assert any(
        getattr(dependency.dependency, 'perm', None) == 'pipeline:prompt:list'
        for dependency in prompt_routes[('/pipeline/prompts', ('GET',))].dependencies
    )
