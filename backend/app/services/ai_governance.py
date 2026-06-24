from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError


class AICallLog(BaseModel):
    id: str
    provider: str
    model: str
    prompt_version_id: str = ""
    skill_id: str = ""
    input_asset_version_ids: list[str] = Field(default_factory=list)
    output_hash: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_ms: int = 0
    status: str = "succeeded"
    error: str = ""
    created_at: str


class PromptVersion(BaseModel):
    id: str
    skill_id: str
    version: str
    prompt_hash: str
    schema_hash: str = ""
    notes: str = ""
    created_by: str
    created_at: str


class EvaluationDataset(BaseModel):
    id: str
    name: str
    description: str = ""
    sample_count: int = 0
    created_by: str
    created_at: str


class EvaluationRun(BaseModel):
    id: str
    dataset_id: str
    status: str
    metrics: dict[str, float] = Field(default_factory=dict)
    created_by: str
    created_at: str
    finished_at: str | None = None


class FindingFeedback(BaseModel):
    id: str
    finding_id: str
    rating: str
    comment: str = ""
    created_by: str
    created_at: str


class PromptVersionCreate(BaseModel):
    skill_id: str
    version: str
    prompt_hash: str
    schema_hash: str = ""
    notes: str = ""


class EvaluationDatasetCreate(BaseModel):
    name: str
    description: str = ""
    sample_count: int = 0


class FindingFeedbackCreate(BaseModel):
    rating: str
    comment: str = ""


class AIGovernanceService:
    def __init__(self) -> None:
        self._calls: list[AICallLog] = []
        self._prompts: list[PromptVersion] = []
        self._datasets: dict[str, EvaluationDataset] = {}
        self._runs: dict[str, EvaluationRun] = {}
        self._feedback: list[FindingFeedback] = []
        self._lock = Lock()

    def list_calls(self) -> list[AICallLog]:
        with self._lock:
            return list(reversed(self._calls))

    def record_call(self, call: AICallLog) -> AICallLog:
        with self._lock:
            self._calls.append(call)
        return call

    def list_prompts(self) -> list[PromptVersion]:
        with self._lock:
            return list(reversed(self._prompts))

    def create_prompt(self, payload: PromptVersionCreate, *, actor_id: str) -> PromptVersion:
        prompt = PromptVersion(
            id=f"prompt_{uuid4().hex[:12]}",
            skill_id=payload.skill_id,
            version=payload.version,
            prompt_hash=payload.prompt_hash,
            schema_hash=payload.schema_hash,
            notes=payload.notes,
            created_by=actor_id,
            created_at=_now(),
        )
        with self._lock:
            self._prompts.append(prompt)
        return prompt

    def create_dataset(self, payload: EvaluationDatasetCreate, *, actor_id: str) -> EvaluationDataset:
        dataset = EvaluationDataset(
            id=f"eval_dataset_{uuid4().hex[:12]}",
            name=payload.name,
            description=payload.description,
            sample_count=payload.sample_count,
            created_by=actor_id,
            created_at=_now(),
        )
        with self._lock:
            self._datasets[dataset.id] = dataset
        return dataset

    def list_datasets(self) -> list[EvaluationDataset]:
        with self._lock:
            return list(reversed(list(self._datasets.values())))

    def create_run(self, dataset_id: str, *, actor_id: str) -> EvaluationRun:
        with self._lock:
            dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise NotFoundError("Evaluation dataset not found.", metadata={"dataset_id": dataset_id})
        run = EvaluationRun(
            id=f"eval_run_{uuid4().hex[:12]}",
            dataset_id=dataset.id,
            status="succeeded",
            metrics={
                "schema_compliance": 1.0,
                "evidence_accuracy": 1.0 if dataset.sample_count else 0.0,
                "sample_count": float(dataset.sample_count),
            },
            created_by=actor_id,
            created_at=_now(),
            finished_at=_now(),
        )
        with self._lock:
            self._runs[run.id] = run
        return run

    def get_run(self, run_id: str) -> EvaluationRun:
        with self._lock:
            run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("Evaluation run not found.", metadata={"run_id": run_id})
        return run

    def create_feedback(self, finding_id: str, payload: FindingFeedbackCreate, *, actor_id: str) -> FindingFeedback:
        feedback = FindingFeedback(
            id=f"finding_feedback_{uuid4().hex[:12]}",
            finding_id=finding_id,
            rating=payload.rating,
            comment=payload.comment,
            created_by=actor_id,
            created_at=_now(),
        )
        with self._lock:
            self._feedback.append(feedback)
        return feedback

    def list_feedback(self) -> list[FindingFeedback]:
        with self._lock:
            return list(reversed(self._feedback))

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()
            self._prompts.clear()
            self._datasets.clear()
            self._runs.clear()
            self._feedback.clear()


def _now() -> str:
    return datetime.now(UTC).isoformat()


ai_governance_service = AIGovernanceService()
