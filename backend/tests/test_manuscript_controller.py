from app.research.api.manuscript_controller import manuscript_controller


def test_manuscript_controller_exposes_generation_routes() -> None:
    routes = {(route.path, tuple(sorted(route.methods))) for route in manuscript_controller.routes}

    assert ('/manuscript/generate', ('POST',)) in routes
    assert ('/manuscript/jobs', ('GET',)) in routes
    assert ('/manuscript/jobs/{job_id}', ('GET',)) in routes
    assert ('/manuscript/jobs/{job_id}/export', ('GET',)) in routes
    assert ('/manuscript/titles/suggest', ('POST',)) in routes
