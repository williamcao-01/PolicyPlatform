from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.services.ai_governance import (
    AICallLog,
    EvaluationDataset,
    EvaluationDatasetCreate,
    EvaluationRun,
    FindingFeedback,
    FindingFeedbackCreate,
    PromptVersion,
    PromptVersionCreate,
    ai_governance_service,
)
from app.services.audit import audit_service
from app.services.auth import Principal


router = APIRouter(prefix="/api", tags=["ai-governance"])


@router.get("/ai/calls", response_model=list[AICallLog])
def ai_calls(_: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ))) -> list[AICallLog]:
    return ai_governance_service.list_calls()


@router.get("/ai/prompts", response_model=list[PromptVersion])
def prompt_versions(_: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ))) -> list[PromptVersion]:
    return ai_governance_service.list_prompts()


@router.post("/ai/prompts", response_model=PromptVersion)
def create_prompt_version(
    payload: PromptVersionCreate,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ)),
) -> PromptVersion:
    prompt = ai_governance_service.create_prompt(payload, actor_id=principal.id)
    _audit(request, principal, "ai.prompt.create", "prompt_version", prompt.id)
    return prompt


@router.get("/evaluations/datasets", response_model=list[EvaluationDataset])
def evaluation_datasets(_: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ))) -> list[EvaluationDataset]:
    return ai_governance_service.list_datasets()


@router.post("/evaluations/datasets", response_model=EvaluationDataset)
def create_evaluation_dataset(
    payload: EvaluationDatasetCreate,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ)),
) -> EvaluationDataset:
    dataset = ai_governance_service.create_dataset(payload, actor_id=principal.id)
    _audit(request, principal, "ai.evaluation_dataset.create", "evaluation_dataset", dataset.id)
    return dataset


@router.post("/evaluations/runs", response_model=EvaluationRun)
def create_evaluation_run(
    dataset_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.SKILL_RUN)),
) -> EvaluationRun:
    run = ai_governance_service.create_run(dataset_id, actor_id=principal.id)
    _audit(request, principal, "ai.evaluation_run.create", "evaluation_run", run.id)
    return run


@router.get("/evaluations/runs/{run_id}", response_model=EvaluationRun)
def evaluation_run(
    run_id: str,
    _: Principal = Depends(require_permission(Permission.SKILL_AUDIT_READ)),
) -> EvaluationRun:
    return ai_governance_service.get_run(run_id)


@router.post("/findings/{finding_id}/feedback", response_model=FindingFeedback)
def create_finding_feedback(
    finding_id: str,
    payload: FindingFeedbackCreate,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.FINDING_UPDATE)),
) -> FindingFeedback:
    feedback = ai_governance_service.create_feedback(finding_id, payload, actor_id=principal.id)
    _audit(request, principal, "finding.feedback.create", "finding", finding_id)
    return feedback


def _audit(request: Request, principal: Principal, action: str, object_type: str, object_id: str) -> None:
    audit_service.record(
        actor_id=principal.id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        request_id=request.headers.get("x-request-id"),
    )
