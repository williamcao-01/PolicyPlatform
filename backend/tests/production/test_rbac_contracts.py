from __future__ import annotations

from app.main import app

from .helpers import PROTECTED_ROUTE_CONTRACT, RBAC_MATRIX, RBAC_PERMISSIONS, RBAC_ROLES


def test_rbac_roles_permissions_and_matrix_are_well_formed() -> None:
    matrix_roles = {rule.role for rule in RBAC_MATRIX}

    assert matrix_roles == RBAC_ROLES
    assert len(matrix_roles) == len(RBAC_MATRIX)
    for rule in RBAC_MATRIX:
        assert rule.permissions
        assert rule.permissions <= RBAC_PERMISSIONS


def test_rbac_least_privilege_baseline() -> None:
    permissions_by_role = {rule.role: rule.permissions for rule in RBAC_MATRIX}

    assert "rbac:manage" in permissions_by_role["system_admin"]
    assert "rbac:manage" not in permissions_by_role["institution_admin"]
    assert "asset:approve" not in permissions_by_role["business_owner"]
    assert "skill:run" not in permissions_by_role["auditor"]
    assert permissions_by_role["viewer"] == {"asset:read", "finding:read"}


def test_protected_route_contract_targets_existing_routes() -> None:
    existing_routes = {(method, route.path) for route in app.routes for method in getattr(route, "methods", set())}

    for route_key, permission in PROTECTED_ROUTE_CONTRACT.items():
        assert route_key in existing_routes
        assert permission in RBAC_PERMISSIONS


def test_mutating_and_audit_routes_require_permission_dependencies() -> None:
    route_by_key = {
        (method, route.path): route
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    for route_key in PROTECTED_ROUTE_CONTRACT:
        dependant = getattr(route_by_key[route_key], "dependant", None)
        assert dependant is not None
        assert dependant.dependencies, f"{route_key} has no RBAC dependency"
