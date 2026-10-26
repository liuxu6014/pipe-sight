"""管网业务 API 聚合入口。"""

from app.intelligence.api.controller import controller as _intelligence_controller
from app.intelligence.api.collection_controller import collection_controller as _collection_controller
from app.library.api.controller import controller as _library_controller
from app.research.api.controller import controller as _research_controller
from common.http.routing import APIRouterPro

pipeline_controller = APIRouterPro(
    prefix='',
    order_num=30,
    tags=['管网情报'],
)
pipeline_controller.include_router(_intelligence_controller)
pipeline_controller.include_router(_collection_controller)
pipeline_controller.include_router(_library_controller)
pipeline_controller.include_router(_research_controller)

__all__ = ['pipeline_controller']
