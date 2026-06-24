from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_login_me_and_refresh_contract() -> None:
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "admin"
    assert "rbac:manage" in body["user"]["permissions"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]

    refresh = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


def test_login_rejects_invalid_password() -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_me_requires_bearer_token() -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_permissions_endpoint_exposes_permission_codes_not_role_names_only() -> None:
    response = client.get("/api/permissions")

    assert response.status_code == 200
    body = response.json()
    assert "system_admin" in body["roles"]
    assert "asset:read" in body["permissions"]
    assert "rbac:manage" in body["matrix"]["system_admin"]
    assert "rbac:manage" not in body["matrix"]["viewer"]


def test_audit_logs_are_permission_protected() -> None:
    viewer_login = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert viewer_login.status_code == 200
    viewer_token = viewer_login.json()["access_token"]

    denied = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {viewer_token}"})
    assert denied.status_code == 403
    assert denied.json()["code"] == "permission_denied"

    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    allowed = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})

    assert allowed.status_code == 200
    assert any(event["action"] == "auth.login" for event in allowed.json())
