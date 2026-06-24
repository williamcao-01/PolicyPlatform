from __future__ import annotations

import os
from threading import Lock

from pydantic import BaseModel


class KnowledgeBaseConfig(BaseModel):
    enabled: bool
    api_url: str
    has_api_key: bool = False


class KnowledgeBaseConfigUpdate(BaseModel):
    enabled: bool | None = None
    api_url: str | None = None


class SystemSettings(BaseModel):
    knowledge_base: KnowledgeBaseConfig


class SystemSettingsService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._knowledge_base = KnowledgeBaseConfig(
            enabled=os.getenv("KNOWLEDGE_BASE_ENABLED", "false").lower() == "true",
            api_url=os.getenv("KNOWLEDGE_API_URL", "http://127.0.0.1:8765"),
            has_api_key=bool(os.getenv("KNOWLEDGE_API_KEY", "")),
        )

    def get(self) -> SystemSettings:
        with self._lock:
            return SystemSettings(knowledge_base=self._knowledge_base.model_copy())

    def update_knowledge_base(self, payload: KnowledgeBaseConfigUpdate) -> KnowledgeBaseConfig:
        with self._lock:
            next_config = self._knowledge_base.model_copy()
            if payload.enabled is not None:
                next_config.enabled = payload.enabled
            if payload.api_url is not None:
                next_config.api_url = payload.api_url
            self._knowledge_base = next_config
            return self._knowledge_base.model_copy()

    def reset_from_environment(self) -> None:
        with self._lock:
            self._knowledge_base = KnowledgeBaseConfig(
                enabled=os.getenv("KNOWLEDGE_BASE_ENABLED", "false").lower() == "true",
                api_url=os.getenv("KNOWLEDGE_API_URL", "http://127.0.0.1:8765"),
                has_api_key=bool(os.getenv("KNOWLEDGE_API_KEY", "")),
            )


system_settings_service = SystemSettingsService()
