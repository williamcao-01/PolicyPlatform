from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.exceptions import InvalidStateTransitionError, NotFoundError


ASSET_LIFECYCLE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("draft", "in_review"),
        ("in_review", "approved"),
        ("in_review", "rejected"),
        ("rejected", "draft"),
        ("approved", "published"),
        ("published", "archived"),
    }
)
ASSET_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {"draft", "in_review", "approved", "published", "archived", "rejected"}
)


class AssetLifecycleRecord(BaseModel):
    id: str
    asset_id: str
    asset_type: str = "generic"
    status: str
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str
    history: list[dict[str, str]] = Field(default_factory=list)


class AssetLifecycleService:
    def __init__(self) -> None:
        self._records: dict[str, AssetLifecycleRecord] = {}
        self._lock = Lock()

    def ensure_asset(self, asset_id: str, *, actor_id: str, asset_type: str = "generic") -> AssetLifecycleRecord:
        with self._lock:
            record = self._records.get(asset_id)
            if record:
                return record
            now = _now()
            record = AssetLifecycleRecord(
                id=f"asset_lifecycle_{uuid4().hex[:12]}",
                asset_id=asset_id,
                asset_type=asset_type,
                status="draft",
                created_by=actor_id,
                updated_by=actor_id,
                created_at=now,
                updated_at=now,
                history=[
                    {
                        "from": "",
                        "to": "draft",
                        "actor_id": actor_id,
                        "at": now,
                        "reason": "created",
                    }
                ],
            )
            self._records[asset_id] = record
            return record

    def get(self, asset_id: str) -> AssetLifecycleRecord:
        with self._lock:
            record = self._records.get(asset_id)
        if not record:
            raise NotFoundError("Asset lifecycle record not found.", metadata={"asset_id": asset_id})
        return record

    def transition(self, asset_id: str, target: str, *, actor_id: str, reason: str = "") -> AssetLifecycleRecord:
        if target not in ASSET_LIFECYCLE_STATES:
            raise InvalidStateTransitionError("Unknown asset lifecycle target.", metadata={"target": target})
        record = self.ensure_asset(asset_id, actor_id=actor_id)
        current = record.status
        if current == target:
            return record
        if (current, target) not in ASSET_LIFECYCLE_TRANSITIONS:
            raise InvalidStateTransitionError(
                "Invalid asset lifecycle transition.",
                metadata={"asset_id": asset_id, "current": current, "target": target},
            )
        now = _now()
        record.status = target
        record.updated_by = actor_id
        record.updated_at = now
        record.history.append(
            {
                "from": current,
                "to": target,
                "actor_id": actor_id,
                "at": now,
                "reason": reason,
            }
        )
        with self._lock:
            self._records[asset_id] = record
        return record

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


def _now() -> str:
    return datetime.now(UTC).isoformat()


asset_lifecycle_service = AssetLifecycleService()
