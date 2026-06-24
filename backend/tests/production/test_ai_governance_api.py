from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_governance import ai_governance_service


client = TestClient(app)


def setup_function() -> None:
    ai_governance_service.clear()


def _token(username: str = "admin", password: str = "admin123") -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_prompt_dataset_run_and_feedback_flow() -> None:
    token = _token()

    prompt = client.post(
        "/api/ai/prompts",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": "skill_policy_conflict", "version": "v1", "prompt_hash": "hash_prompt"},
    )
    assert prompt.status_code == 200
    assert prompt.json()["skill_id"] == "skill_policy_conflict"

    prompts = client.get("/api/ai/prompts", headers={"Authorization": f"Bearer {token}"})
    assert prompts.status_code == 200
    assert prompts.json()[0]["prompt_hash"] == "hash_prompt"

    dataset = client.post(
        "/api/evaluations/datasets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "核心核验集", "description": "采购与流程一致性", "sample_count": 3},
    )
    assert dataset.status_code == 200
    dataset_id = dataset.json()["id"]

    run = client.post(
        "/api/evaluations/runs",
        headers={"Authorization": f"Bearer {token}"},
        params={"dataset_id": dataset_id},
    )
    assert run.status_code == 200
    assert run.json()["metrics"]["schema_compliance"] == 1.0

    run_detail = client.get(f"/api/evaluations/runs/{run.json()['id']}", headers={"Authorization": f"Bearer {token}"})
    assert run_detail.status_code == 200
    assert run_detail.json()["dataset_id"] == dataset_id

    feedback = client.post(
        "/api/findings/finding_demo/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={"rating": "useful", "comment": "证据可定位"},
    )
    assert feedback.status_code == 200
    assert feedback.json()["finding_id"] == "finding_demo"


def test_ai_governance_routes_reject_viewer_for_writes() -> None:
    token = _token("viewer", "viewer123")

    response = client.post(
        "/api/evaluations/datasets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "viewer cannot create"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
