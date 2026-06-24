from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.services.assets import AssetLifecycleRecord, asset_lifecycle_service
from app.services.audit import audit_service
from app.services.auth import Principal


router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/{asset_id}/submit-review", response_model=AssetLifecycleRecord)
def submit_review(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.ASSET_SUBMIT_REVIEW)),
) -> AssetLifecycleRecord:
    record = asset_lifecycle_service.transition(asset_id, "in_review", actor_id=principal.id, reason="submit_review")
    _audit(request, principal, "asset.submit_review", asset_id)
    return record


@router.post("/{asset_id}/approve", response_model=AssetLifecycleRecord)
def approve(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.ASSET_APPROVE)),
) -> AssetLifecycleRecord:
    record = asset_lifecycle_service.transition(asset_id, "approved", actor_id=principal.id, reason="approve")
    _audit(request, principal, "asset.approve", asset_id)
    return record


@router.post("/{asset_id}/publish", response_model=AssetLifecycleRecord)
def publish(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.ASSET_PUBLISH)),
) -> AssetLifecycleRecord:
    record = asset_lifecycle_service.transition(asset_id, "published", actor_id=principal.id, reason="publish")
    _audit(request, principal, "asset.publish", asset_id)
    return record


@router.post("/{asset_id}/archive", response_model=AssetLifecycleRecord)
def archive(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.ASSET_ARCHIVE)),
) -> AssetLifecycleRecord:
    record = asset_lifecycle_service.transition(asset_id, "archived", actor_id=principal.id, reason="archive")
    _audit(request, principal, "asset.archive", asset_id)
    return record


def _audit(request: Request, principal: Principal, action: str, asset_id: str) -> None:
    audit_service.record(
        actor_id=principal.id,
        action=action,
        object_type="asset",
        object_id=asset_id,
        request_id=request.headers.get("x-request-id"),
    )
