from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.assets import asset_lifecycle_service


client = TestClient(app)


def setup_function() -> None:
    asset_lifecycle_service.clear()


def _token(username: str = "admin", password: str = "admin123") -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_asset_lifecycle_main_path() -> None:
    token = _token()
    asset_id = "policy_demo_asset"

    submitted = client.post(f"/api/assets/{asset_id}/submit-review", headers={"Authorization": f"Bearer {token}"})
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "in_review"

    approved = client.post(f"/api/assets/{asset_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    published = client.post(f"/api/assets/{asset_id}/publish", headers={"Authorization": f"Bearer {token}"})
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    archived = client.post(f"/api/assets/{asset_id}/archive", headers={"Authorization": f"Bearer {token}"})
    assert archived.status_code == 200
    body = archived.json()
    assert body["status"] == "archived"
    assert [item["to"] for item in body["history"]] == ["draft", "in_review", "approved", "published", "archived"]


def test_asset_lifecycle_rejects_invalid_transition() -> None:
    token = _token()
    response = client.post("/api/assets/asset_skip_publish/publish", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state_transition"


def test_asset_lifecycle_permissions_are_action_specific() -> None:
    business_owner_token = _token("viewer", "viewer123")
    response = client.post(
        "/api/assets/asset_viewer/submit-review",
        headers={"Authorization": f"Bearer {business_owner_token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
