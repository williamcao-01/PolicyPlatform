from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: Sequence[LLMMessage]
    model: str | None = None
    temperature: float = 0.0
    response_format: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...


class DisabledLLMProvider:
    def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("No LLM provider is configured.")


class StaticLLMProvider:
    """Deterministic provider useful for tests and local wiring."""

    def __init__(self, content: str = "") -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.content, model=request.model)
