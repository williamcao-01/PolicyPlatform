from __future__ import annotations

from typing import get_args

from app.models import FindingStatus, RoleMapping, SkillRunResult, VersionStatus

from .helpers import ASSET_STATE_MACHINE, ASYNC_TASK_STATE_MACHINE, TransitionSpec


def test_model_status_literals_are_stable() -> None:
    assert set(get_args(FindingStatus)) == {"pending_review", "in_progress", "closed", "rejected"}
    assert set(get_args(VersionStatus)) == {"current", "historical"}
    assert set(get_args(SkillRunResult.model_fields["status"].annotation)) == {"completed", "failed"}
    assert set(get_args(RoleMapping.model_fields["status"].annotation)) == {"mapped", "unmapped", "ignored"}


def test_asset_lifecycle_contract_is_well_formed() -> None:
    assert_transition_spec_is_well_formed(ASSET_STATE_MACHINE)
    assert ("draft", "published") not in ASSET_STATE_MACHINE.transitions
    assert ("approved", "published") in ASSET_STATE_MACHINE.transitions
    assert ASSET_STATE_MACHINE.terminal == {"archived"}


def test_async_task_lifecycle_contract_is_well_formed() -> None:
    assert_transition_spec_is_well_formed(ASYNC_TASK_STATE_MACHINE)
    assert ("queued", "succeeded") not in ASYNC_TASK_STATE_MACHINE.transitions
    assert ("running", "succeeded") in ASYNC_TASK_STATE_MACHINE.transitions
    assert ASYNC_TASK_STATE_MACHINE.terminal == {"succeeded", "failed", "cancelled"}


def assert_transition_spec_is_well_formed(spec: TransitionSpec) -> None:
    assert spec.name
    assert spec.initial in spec.states
    assert spec.terminal <= spec.states
    assert spec.transitions
    for source, target in spec.transitions:
        assert source in spec.states
        assert target in spec.states
        assert source not in spec.terminal
        assert source != target
