"""Compatibility import for the migrated application factory."""

from app.bootstrap import (
    _start_background_tasks,
    _stop_background_tasks,
    create_app,
    lifespan,
)

__all__ = ['_start_background_tasks', '_stop_background_tasks', 'create_app', 'lifespan']
