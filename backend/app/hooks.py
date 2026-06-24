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
        _mirror_ai_audit_event(event)
        return event

    def clear(self) -> None:
        self.events.clear()


hooks = HookRegistry()


def _mirror_ai_audit_event(event: HookEvent) -> None:
    if event.name not in {"after_llm_call", "skill_run_failed", "upload_analysis_fallback", "finding_verification_failed"}:
        return
    try:
        from app.services.ai_governance import AICallLog, ai_governance_service
    except Exception:
        return
    status = "succeeded" if event.name == "after_llm_call" else "failed"
    ai_governance_service.record_call(
        AICallLog(
            id=f"ai_call_{event.id.removeprefix('hook_')}",
            provider=str(event.payload.get("provider") or "deepseek" if event.payload.get("model") else "system"),
            model=str(event.payload.get("model") or ""),
            skill_id=str(event.payload.get("skill_id") or ""),
            status=status,
            error=str(event.payload.get("reason") or ""),
            created_at=event.created_at,
        )
    )
