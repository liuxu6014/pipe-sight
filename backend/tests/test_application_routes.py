from app.entrypoints.routes import _routers_from_module
from app.intelligence.api import pipeline_controller


def test_aggregated_pipeline_module_registers_only_its_own_router() -> None:
    routers = _routers_from_module(pipeline_controller)

    assert [(name, router) for name, router in routers] == [
        ('pipeline_controller', pipeline_controller.pipeline_controller)
    ]
