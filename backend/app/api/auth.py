from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.dependencies import current_principal_dependency
from app.core.permissions import Permission, Role, permission_matrix
from app.services.audit import audit_service
from app.services.auth import Principal, auth_service


router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Principal


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request) -> AuthResponse:
    principal, access_token, refresh_token = auth_service.authenticate(payload.username, payload.password)
    audit_service.record(
        actor_id=principal.id,
        action="auth.login",
        object_type="user",
        object_id=principal.id,
        request_id=request.headers.get("x-request-id"),
    )
    return AuthResponse(access_token=access_token, refresh_token=refresh_token, user=principal)


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, request: Request) -> AuthResponse:
    principal, access_token, refresh_token = auth_service.refresh(payload.refresh_token)
    audit_service.record(
        actor_id=principal.id,
        action="auth.refresh",
        object_type="user",
        object_id=principal.id,
        request_id=request.headers.get("x-request-id"),
    )
    return AuthResponse(access_token=access_token, refresh_token=refresh_token, user=principal)


@router.post("/auth/logout")
def logout(
    request: Request,
    principal: Principal = Depends(current_principal_dependency),
) -> dict:
    audit_service.record(
        actor_id=principal.id,
        action="auth.logout",
        object_type="user",
        object_id=principal.id,
        request_id=request.headers.get("x-request-id"),
    )
    return {"status": "ok"}


@router.get("/auth/me", response_model=Principal)
def me(principal: Principal = Depends(current_principal_dependency)) -> Principal:
    return principal


@router.get("/permissions")
def permissions() -> dict:
    return {
        "roles": [role.value for role in Role],
        "permissions": [permission.value for permission in Permission],
        "matrix": permission_matrix(),
    }
