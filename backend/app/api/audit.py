from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.services.audit import AuditEvent, audit_service
from app.services.auth import Principal


router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit-logs", response_model=list[AuditEvent])
def audit_logs(
    _: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ)),
) -> list[AuditEvent]:
    return audit_service.list_events()
