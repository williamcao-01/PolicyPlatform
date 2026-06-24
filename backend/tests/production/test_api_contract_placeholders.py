from __future__ import annotations

from app.main import app

from .helpers import MAIN_CHAIN_ROUTES, PLANNED_ASSET_LIFECYCLE_ROUTES, PLANNED_ASYNC_TASK_ROUTES


def _route_keys() -> set[tuple[str, str]]:
    return {(method, route.path) for route in app.routes for method in getattr(route, "methods", set())}


def test_main_chain_api_routes_are_registered() -> None:
    existing_routes = _route_keys()

    missing = MAIN_CHAIN_ROUTES - existing_routes
    assert not missing


def test_planned_async_task_routes_are_registered() -> None:
    existing_routes = _route_keys()

    missing = PLANNED_ASYNC_TASK_ROUTES - existing_routes
    assert not missing


def test_planned_asset_lifecycle_routes_are_registered() -> None:
    existing_routes = _route_keys()

    missing = PLANNED_ASSET_LIFECYCLE_ROUTES - existing_routes
    assert not missing
