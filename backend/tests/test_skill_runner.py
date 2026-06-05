import os

from app.models import SkillRunRequest
from app.skill_runner import run_skill
from app.store import store

KB_UNAVAILABLE_Q = "专业知识库当前不可用。是否允许本次仅基于制度和流程证据先生成待复核结论？"


def setup_function() -> None:
    os.environ["KNOWLEDGE_API_URL"] = "http://127.0.0.1:9"
    os.environ["KNOWLEDGE_BASE_ENABLED"] = "true"
    os.environ["USE_REAL_LLM"] = "false"
    store.reset()


def test_skill_pauses_before_publishing_findings_when_confirmation_is_needed() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_policy_conflict",
            policy_ids=["policy_purchase", "policy_sub_purchase"],
        )
    )

    assert result.status == "completed"
    assert result.findings == []
    assert result.questions
    assert result.questions[0].source == "knowledge_base"
    assert "确认前不会输出风险结论" in result.final_answer
    assert store.all("findings") == []


def test_policy_conflict_demo_finds_threshold_conflict_after_confirmation() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_policy_conflict",
            policy_ids=["policy_purchase", "policy_sub_purchase"],
            clarification_answers={KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        )
    )

    assert result.status == "completed"
    assert result.findings[0].finding_type == "policy_conflict"
    assert result.findings[0].evidence[0].source_type == "policy_clause"
    assert result.questions == []


def test_policy_process_demo_finds_missing_and_extra_nodes() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_policy_process_check",
            policy_ids=["policy_purchase"],
            process_ids=["process_purchase"],
            clarification_answers={KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        )
    )

    finding_types = {finding.finding_type for finding in result.findings}
    assert "missing_process_node" in finding_types
    assert "extra_process_node" in finding_types
    assert any(ev.source_type == "bpmn_node" for finding in result.findings for ev in finding.evidence)


def test_no_policy_basis_demo_finds_salary_node() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_no_policy_basis",
            policy_ids=["policy_recruit", "policy_salary"],
            process_ids=["process_recruit"],
            clarification_answers={KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        )
    )

    assert len(result.findings) >= 3
    titles = [finding.title for finding in result.findings]
    assert any("定薪审批" in title for title in titles)
    assert any(finding.finding_type == "no_policy_basis" for finding in result.findings)
    assert any(finding.severity == "high" for finding in result.findings)


def test_skill_result_reports_knowledge_base_unavailable_question() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_policy_process_check",
            policy_ids=["policy_purchase"],
            process_ids=["process_purchase"],
        )
    )

    assert any(question.source == "knowledge_base" for question in result.questions)
    assert "专业知识库" in result.summary


def test_skill_result_acknowledges_clarification_answers() -> None:
    result = run_skill(
        SkillRunRequest(
            skill_id="skill_policy_process_check",
            policy_ids=["policy_purchase"],
            process_ids=["process_purchase"],
            clarification_answers={KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        )
    )

    assert result.status == "completed"
    assert result.findings
    assert "已结合用户补充信息继续执行" in result.summary
