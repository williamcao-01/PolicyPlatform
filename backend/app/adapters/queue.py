from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from app.core.exceptions import ExternalServiceError


@dataclass(frozen=True)
class QueueMessage:
    id: str
    topic: str
    payload: dict[str, Any]
    headers: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class QueueAdapter(Protocol):
    def publish(self, topic: str, payload: dict[str, Any], *, headers: Mapping[str, str] | None = None) -> QueueMessage:
        ...

    def consume(self, topic: str, *, max_messages: int = 1) -> list[QueueMessage]:
        ...

    def ack(self, message: QueueMessage) -> None:
        ...


class InMemoryQueueAdapter:
    def __init__(self) -> None:
        self._messages: dict[str, deque[QueueMessage]] = defaultdict(deque)
        self._acked: set[str] = set()

    def publish(self, topic: str, payload: dict[str, Any], *, headers: Mapping[str, str] | None = None) -> QueueMessage:
        message = QueueMessage(id=str(uuid4()), topic=topic, payload=payload, headers=headers or {})
        self._messages[topic].append(message)
        return message

    def consume(self, topic: str, *, max_messages: int = 1) -> list[QueueMessage]:
        messages: list[QueueMessage] = []
        for _ in range(max_messages):
            if not self._messages[topic]:
                break
            messages.append(self._messages[topic].popleft())
        return messages

    def ack(self, message: QueueMessage) -> None:
        self._acked.add(message.id)

    @property
    def acked_message_ids(self) -> frozenset[str]:
        return frozenset(self._acked)


class RocketMQQueueAdapter:
    """RocketMQ adapter boundary.

    The concrete organization-approved RocketMQ Python client can be wired here without
    leaking SDK calls into services or API routers.
    """

    def __init__(self, url: str, *, producer_group: str = "policy-assistant-producer") -> None:
        self.url = url
        self.producer_group = producer_group
        try:
            import rocketmq  # type: ignore[import-not-found]  # noqa: F401
        except Exception as exc:
            raise ExternalServiceError(
                "RocketMQ provider is configured but no RocketMQ Python client is installed.",
                metadata={"queue_url": url, "provider": "rocketmq"},
            ) from exc

    def publish(self, topic: str, payload: dict[str, Any], *, headers: Mapping[str, str] | None = None) -> QueueMessage:
        raise ExternalServiceError("RocketMQ publish is not wired to a concrete client yet.", metadata={"topic": topic})

    def consume(self, topic: str, *, max_messages: int = 1) -> list[QueueMessage]:
        raise ExternalServiceError("RocketMQ consume is not wired to a concrete client yet.", metadata={"topic": topic})

    def ack(self, message: QueueMessage) -> None:
        raise ExternalServiceError("RocketMQ ack is not wired to a concrete client yet.", metadata={"message_id": message.id})
