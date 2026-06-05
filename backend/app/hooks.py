from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class HookEvent:
    id: str
    name: str
    payload: dict[str, Any]
    created_at: str


@dataclass
class HookRegistry:
    events: list[HookEvent] = field(default_factory=list)

    def emit(self, name: str, payload: dict[str, Any]) -> HookEvent:
        event = HookEvent(
            id=f"hook_{uuid4().hex[:10]}",
            name=name,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.events.append(event)
        return event

    def clear(self) -> None:
        self.events.clear()


hooks = HookRegistry()

