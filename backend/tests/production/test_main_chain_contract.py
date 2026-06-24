from __future__ import annotations

from app.models import SkillRunRequest
from app.skill_registry import list_skill_definitions


def test_skill_run_request_contract_supports_main_chain_inputs() -> None:
    request = SkillRunRequest(
        skill_id="skill_policy_process_check",
        policy_ids=["policy_purchase"],
        process_ids=["process_purchase"],
        knowledge_node_ids=["role_platform_manager"],
        clarification_answers={"question": "answer"},
    )

    assert request.skill_id == "skill_policy_process_check"
    assert request.policy_ids == ["policy_purchase"]
    assert request.process_ids == ["process_purchase"]
    assert request.knowledge_node_ids == ["role_platform_manager"]
    assert request.clarification_answers == {"question": "answer"}


def test_registered_skill_contract_contains_main_chain_capabilities() -> None:
    skills = {skill.id: skill for skill in list_skill_definitions()}

    assert "skill_policy_process_check" in skills
    assert "skill_policy_conflict" in skills
    assert "skill_upload_policy_file" in skills
    assert skills["skill_upload_policy_file"].can_update_assets is True
    assert "policy_document" in skills["skill_upload_policy_file"].output_types

