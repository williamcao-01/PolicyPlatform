from __future__ import annotations

from fastapi.testclient import TestClient

from app.knowledge_base import KnowledgeBaseClient
from app.main import app
from app.services.system_settings import KnowledgeBaseConfigUpdate, system_settings_service


client = TestClient(app)


def setup_function() -> None:
    system_settings_service.reset_from_environment()
    system_settings_service.update_knowledge_base(KnowledgeBaseConfigUpdate(enabled=False))


def test_knowledge_base_is_disabled_by_default_for_production_controls() -> None:
    response = client.get("/api/system/settings")

    assert response.status_code == 200
    assert response.json()["knowledge_base"]["enabled"] is False
    assert KnowledgeBaseClient().ask("test")["reason"] == "disabled"


def test_knowledge_base_can_be_toggled_from_system_settings() -> None:
    enable = client.patch("/api/system/settings/knowledge-base", json={"enabled": True, "api_url": "http://127.0.0.1:9"})

    assert enable.status_code == 200
    assert enable.json()["enabled"] is True
    assert enable.json()["api_url"] == "http://127.0.0.1:9"

    disable = client.patch("/api/system/settings/knowledge-base", json={"enabled": False})
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False
