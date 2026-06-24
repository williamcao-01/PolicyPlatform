from __future__ import annotations

import inspect

from app.hooks import HookEvent, HookRegistry
from app import finding_verifier, policy_upload, skill_runner

from .helpers import AI_AUDIT_EVENTS, AI_AUDIT_REQUIRED_PAYLOAD_KEYS


def test_ai_audit_event_contract_is_well_formed() -> None:
    assert set(AI_AUDIT_REQUIRED_PAYLOAD_KEYS) == AI_AUDIT_EVENTS
    for event_name, required_keys in AI_AUDIT_REQUIRED_PAYLOAD_KEYS.items():
        assert event_name
        assert required_keys
        assert all(key and key.isidentifier() for key in required_keys)


def test_hook_event_schema_carries_audit_identity_payload_and_timestamp() -> None:
    registry = HookRegistry()

    event = registry.emit("before_llm_call", {"skill_id": "skill_upload_policy_file", "model": "test-model"})

    assert isinstance(event, HookEvent)
    assert event.id.startswith("hook_")
    assert event.name == "before_llm_call"
    assert event.payload["skill_id"] == "skill_upload_policy_file"
    assert event.created_at


def test_current_ai_paths_emit_required_audit_event_names() -> None:
    source = "\n".join(
        [
            inspect.getsource(policy_upload),
            inspect.getsource(skill_runner),
            inspect.getsource(finding_verifier),
        ]
    )

    for event_name in AI_AUDIT_EVENTS:
        assert event_name in source

