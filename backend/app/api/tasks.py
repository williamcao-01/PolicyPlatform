from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.services.audit import audit_service
from app.services.auth import Principal
from app.services.tasks import TaskCreateRequest, TaskLog, TaskRecord, task_service


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskRecord)
def create_task(
    payload: TaskCreateRequest,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> TaskRecord:
    task = task_service.create(payload, requested_by=principal.id)
    _audit(request, principal, "task.create", task.id)
    return task


@router.get("", response_model=list[TaskRecord])
def list_tasks(
    _: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> list[TaskRecord]:
    return task_service.list()


@router.get("/{task_id}", response_model=TaskRecord)
def get_task(
    task_id: str,
    _: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> TaskRecord:
    return task_service.get(task_id)


@router.get("/{task_id}/logs", response_model=list[TaskLog])
def task_logs(
    task_id: str,
    _: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> list[TaskLog]:
    return task_service.logs(task_id)


@router.get("/{task_id}/result")
def task_result(
    task_id: str,
    _: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> dict:
    return task_service.result(task_id)


@router.post("/{task_id}/cancel", response_model=TaskRecord)
def cancel_task(
    task_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> TaskRecord:
    task = task_service.cancel(task_id, actor_id=principal.id)
    _audit(request, principal, "task.cancel", task.id)
    return task


@router.post("/{task_id}/retry", response_model=TaskRecord)
def retry_task(
    task_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> TaskRecord:
    task = task_service.retry(task_id, actor_id=principal.id)
    _audit(request, principal, "task.retry", task.id)
    return task


@router.post("/{task_id}/confirm", response_model=TaskRecord)
def confirm_task(
    task_id: str,
    answers: dict[str, str],
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> TaskRecord:
    task = task_service.confirm(task_id, answers, actor_id=principal.id)
    _audit(request, principal, "task.confirm", task.id)
    return task


def _audit(request: Request, principal: Principal, action: str, task_id: str) -> None:
    audit_service.record(
        actor_id=principal.id,
        action=action,
        object_type="task",
        object_id=task_id,
        request_id=request.headers.get("x-request-id"),
    )
