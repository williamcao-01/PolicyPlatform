from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.adapters.queue import QueueAdapter
from app.core.config import get_settings
from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.core.status import JOB_TRANSITIONS, JobStatus, ensure_transition
from app.services.adapters import build_queue_adapter


class TaskCreateRequest(BaseModel):
    skill_id: str
    policy_ids: list[str] = Field(default_factory=list)
    process_ids: list[str] = Field(default_factory=list)
    knowledge_node_ids: list[str] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    id: str
    skill_id: str
    status: str
    requested_by: str
    policy_ids: list[str] = Field(default_factory=list)
    process_ids: list[str] = Field(default_factory=list)
    knowledge_node_ids: list[str] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)
    queue_message_id: str | None = None
    result: dict | None = None
    error: str = ""
    created_at: str
    updated_at: str


class TaskLog(BaseModel):
    id: str
    task_id: str
    level: str = "info"
    message: str
    created_at: str


class TaskService:
    def __init__(self, queue: QueueAdapter | None = None) -> None:
        self.queue = queue or build_queue_adapter()
        self.topic = get_settings().queue.default_topic
        self._tasks: dict[str, TaskRecord] = {}
        self._logs: dict[str, list[TaskLog]] = {}
        self._lock = Lock()

    def create(self, payload: TaskCreateRequest, *, requested_by: str) -> TaskRecord:
        now = _now()
        task = TaskRecord(
            id=f"task_{uuid4().hex[:12]}",
            skill_id=payload.skill_id,
            status=JobStatus.QUEUED.value,
            requested_by=requested_by,
            policy_ids=payload.policy_ids,
            process_ids=payload.process_ids,
            knowledge_node_ids=payload.knowledge_node_ids,
            clarification_answers=payload.clarification_answers,
            options=payload.options,
            created_at=now,
            updated_at=now,
        )
        message = self.queue.publish(
            self.topic,
            {"task_id": task.id, "skill_id": task.skill_id},
            headers={"requested_by": requested_by},
        )
        task.queue_message_id = message.id
        with self._lock:
            self._tasks[task.id] = task
            self._logs[task.id] = []
        self.log(task.id, f"任务已进入队列：{message.id}")
        return task

    def list(self) -> list[TaskRecord]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            raise NotFoundError("Task not found.", metadata={"task_id": task_id})
        return task

    def logs(self, task_id: str) -> list[TaskLog]:
        self.get(task_id)
        with self._lock:
            return list(self._logs.get(task_id, []))

    def result(self, task_id: str) -> dict:
        task = self.get(task_id)
        return task.result or {"task_id": task.id, "status": task.status}

    def cancel(self, task_id: str, *, actor_id: str) -> TaskRecord:
        task = self.get(task_id)
        return self._transition(task, JobStatus.CANCELLED, actor_id=actor_id, message="任务已取消。")

    def retry(self, task_id: str, *, actor_id: str) -> TaskRecord:
        task = self.get(task_id)
        retried = self._transition(task, JobStatus.QUEUED, actor_id=actor_id, message="任务已重新入队。")
        message = self.queue.publish(self.topic, {"task_id": retried.id, "skill_id": retried.skill_id}, headers={"requested_by": actor_id})
        retried.queue_message_id = message.id
        with self._lock:
            self._tasks[retried.id] = retried
        self.log(retried.id, f"重试消息已发布：{message.id}")
        return retried

    def confirm(self, task_id: str, answers: dict[str, str], *, actor_id: str) -> TaskRecord:
        task = self.get(task_id)
        if task.status != JobStatus.WAITING_CONFIRMATION.value:
            raise InvalidStateTransitionError(
                "Only waiting_confirmation tasks can accept confirmations.",
                metadata={"task_id": task_id, "status": task.status},
            )
        task.clarification_answers.update(answers)
        with self._lock:
            self._tasks[task.id] = task
        return self.retry(task_id, actor_id=actor_id)

    def mark_running(self, task_id: str, *, actor_id: str = "worker") -> TaskRecord:
        return self._transition(self.get(task_id), JobStatus.RUNNING, actor_id=actor_id, message="任务开始执行。")

    def mark_succeeded(self, task_id: str, result: dict, *, actor_id: str = "worker") -> TaskRecord:
        task = self.get(task_id)
        task.result = result
        task.error = ""
        with self._lock:
            self._tasks[task.id] = task
        return self._transition(task, JobStatus.SUCCEEDED, actor_id=actor_id, message="任务执行完成。")

    def mark_failed(self, task_id: str, error: str, *, actor_id: str = "worker") -> TaskRecord:
        task = self.get(task_id)
        task.error = error
        with self._lock:
            self._tasks[task.id] = task
        return self._transition(task, JobStatus.FAILED, actor_id=actor_id, message=f"任务执行失败：{error}")

    def log(self, task_id: str, message: str, *, level: str = "info") -> TaskLog:
        entry = TaskLog(id=f"task_log_{uuid4().hex[:12]}", task_id=task_id, level=level, message=message, created_at=_now())
        with self._lock:
            self._logs.setdefault(task_id, []).append(entry)
        return entry

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._logs.clear()

    def _transition(self, task: TaskRecord, target: JobStatus, *, actor_id: str, message: str) -> TaskRecord:
        current = JobStatus(task.status)
        ensure_transition(current, target, JOB_TRANSITIONS)
        task.status = target.value
        task.updated_at = _now()
        with self._lock:
            self._tasks[task.id] = task
        self.log(task.id, f"{message} 操作人：{actor_id}")
        return task


def _now() -> str:
    return datetime.now(UTC).isoformat()


task_service = TaskService()
