from __future__ import annotations

from app.hooks import HookRegistry
from app.services.ai_governance import ai_governance_service
from app.services.tasks import TaskCreateRequest, TaskService
from app.worker import Worker


def test_worker_drains_memory_queue_and_marks_task_succeeded() -> None:
    service = TaskService()
    task = service.create(TaskCreateRequest(skill_id="skill_policy_conflict"), requested_by="tester")
    worker = Worker(tasks=service, queue=service.queue)

    processed = worker.drain_once()

    assert processed == 1
    result = service.result(task.id)
    assert result["status"] == "succeeded"


def test_ai_hook_events_are_mirrored_to_governance_logs() -> None:
    ai_governance_service.clear()
    registry = HookRegistry()

    registry.emit("after_llm_call", {"skill_id": "skill_upload_policy_file", "model": "deepseek-v4-flash", "finding_count": 0})

    calls = ai_governance_service.list_calls()
    assert calls
    assert calls[0].skill_id == "skill_upload_policy_file"
    assert calls[0].model == "deepseek-v4-flash"
    assert calls[0].status == "succeeded"
