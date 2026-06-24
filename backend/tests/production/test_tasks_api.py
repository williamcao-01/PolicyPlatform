from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.tasks import task_service


client = TestClient(app)


def setup_function() -> None:
    task_service.clear()


def _token(username: str = "admin", password: str = "admin123") -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_task_api_requires_authentication() -> None:
    response = client.post("/api/tasks", json={"skill_id": "skill_policy_conflict"})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_viewer_cannot_create_task() -> None:
    response = client.post(
        "/api/tasks",
        headers={"Authorization": f"Bearer {_token('viewer', 'viewer123')}"},
        json={"skill_id": "skill_policy_conflict"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_create_get_logs_cancel_and_retry_task() -> None:
    token = _token()
    create = client.post(
        "/api/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
        },
    )

    assert create.status_code == 200
    task = create.json()
    assert task["id"].startswith("task_")
    assert task["status"] == "queued"
    assert task["queue_message_id"]

    detail = client.get(f"/api/tasks/{task['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    assert detail.json()["skill_id"] == "skill_policy_conflict"

    logs = client.get(f"/api/tasks/{task['id']}/logs", headers={"Authorization": f"Bearer {token}"})
    assert logs.status_code == 200
    assert any("进入队列" in item["message"] for item in logs.json())

    cancelled = client.post(f"/api/tasks/{task['id']}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retried = client.post(f"/api/tasks/{task['id']}/retry", headers={"Authorization": f"Bearer {token}"})
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"


def test_task_result_returns_status_until_worker_writes_result() -> None:
    token = _token()
    create = client.post(
        "/api/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": "skill_policy_process_check", "policy_ids": ["p1"], "process_ids": ["bpmn1"]},
    )
    task_id = create.json()["id"]

    result = client.get(f"/api/tasks/{task_id}/result", headers={"Authorization": f"Bearer {token}"})

    assert result.status_code == 200
    assert result.json() == {"task_id": task_id, "status": "queued"}
