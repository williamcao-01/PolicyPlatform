from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    request_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: str


class AuditService:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self,
        *,
        actor_id: str,
        action: str,
        object_type: str,
        object_id: str,
        request_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=f"audit_{uuid4().hex[:12]}",
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            metadata=metadata or {},
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._events.append(event)
        return event

    def list_events(self, *, limit: int = 200) -> list[AuditEvent]:
        with self._lock:
            return list(reversed(self._events[-limit:]))

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


audit_service = AuditService()
