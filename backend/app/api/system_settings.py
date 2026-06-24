from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_permission_legacy
from app.core.permissions import Permission
from app.services.audit import audit_service
from app.services.auth import Principal
from app.services.system_settings import KnowledgeBaseConfig, KnowledgeBaseConfigUpdate, SystemSettings, system_settings_service


router = APIRouter(prefix="/api/system", tags=["system-settings"])


@router.get("/settings", response_model=SystemSettings)
def get_system_settings(
    _: Principal = Depends(require_permission_legacy(Permission.RBAC_MANAGE)),
) -> SystemSettings:
    return system_settings_service.get()


@router.patch("/settings/knowledge-base", response_model=KnowledgeBaseConfig)
def update_knowledge_base_settings(
    payload: KnowledgeBaseConfigUpdate,
    request: Request,
    principal: Principal = Depends(require_permission_legacy(Permission.RBAC_MANAGE)),
) -> KnowledgeBaseConfig:
    config = system_settings_service.update_knowledge_base(payload)
    audit_service.record(
        actor_id=principal.id,
        action="system.knowledge_base.update",
        object_type="system_settings",
        object_id="knowledge_base",
        request_id=request.headers.get("x-request-id"),
        metadata={"enabled": str(config.enabled).lower(), "api_url": config.api_url},
    )
    return config
