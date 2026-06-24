from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_legacy_skill_run_still_allows_local_demo_without_token() -> None:
    response = client.post(
        "/api/skill-runs",
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
            "process_ids": [],
            "knowledge_node_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_legacy_hooks_route_has_rbac_dependency_but_local_demo_can_read() -> None:
    response = client.get("/api/hooks/events")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
