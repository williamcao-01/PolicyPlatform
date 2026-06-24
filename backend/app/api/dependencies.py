from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationRequiredError
from app.core.permissions import Permission
from app.services.auth import Principal, auth_service


def settings_dependency() -> Settings:
    return get_settings()


def db_session_dependency() -> Iterator[Any]:
    from app.repositories.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def current_principal_dependency(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization:
        raise AuthenticationRequiredError("缺少认证令牌。")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationRequiredError("认证令牌格式必须为 Bearer token。")
    return auth_service.principal_from_access_token(token)


def optional_principal_dependency(authorization: str | None = Header(default=None)) -> Principal | None:
    if not authorization:
        return None
    return current_principal_dependency(authorization)


def require_permission(permission: Permission):
    def dependency(principal: Principal = Depends(current_principal_dependency)) -> Principal:
        auth_service.require_permission(principal, permission)
        return principal

    return dependency


def require_permission_legacy(permission: Permission):
    def dependency(principal: Principal | None = Depends(optional_principal_dependency)) -> Principal:
        settings = get_settings()
        if principal is None:
            if settings.environment == "production" or settings.auth.enforce_legacy_rbac:
                raise AuthenticationRequiredError("缺少认证令牌。")
            principal = auth_service.bootstrap_principal()
        auth_service.require_permission(principal, permission)
        return principal

    return dependency
