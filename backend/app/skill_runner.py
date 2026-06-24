from __future__ import annotations

from uuid import uuid4

from app.deepseek_client import load_deepseek_settings
from app.finding_verifier import verify_findings
from app.hooks import hooks
from app.models import ClarificationQuestion, Finding, ProfessionalReference, SkillRunRequest, SkillRunResult
from app.rule_engine import run_rule_skill
from app.skill_context import build_skill_context, load_professional_context
from app.skill_llm_runner import run_llm_skill
from app.skill_registry import get_skill_spec
from app.store import store


def _run_id() -> str:
    return f"run_{uuid4().hex[:10]}"


def run_skill(request: SkillRunRequest) -> SkillRunResult:
    skill = store.get_skill(request.skill_id)
    if not skill:
        event = hooks.emit("skill_run_failed", {"skill_id": request.skill_id, "reason": "unknown_skill"})
        return SkillRunResult(id=_run_id(), skill_id=request.skill_id, status="failed", summary="未找到对应 Skill。", findings=[], hook_event_ids=[event.id])

    before = _emit_before_run(request)
    context = build_skill_context(request)
    professional_context, professional_references, questions = _load_professional_inputs(request, context)
    settings = load_deepseek_settings()
    findings = _analyze(request, context, professional_context, professional_references, questions, settings.use_real_llm)
    findings = verify_findings(request, context, findings, settings.use_real_llm)
    findings = _attach_version_context(request, findings)
    unanswered = _unanswered_questions(request, questions)
    paused_for_confirmation = bool(unanswered)
    publishable_findings = [] if paused_for_confirmation else findings
    publishable_questions = unanswered
    event_ids = [before.id] + _publish_findings(publishable_findings)
    event_ids.append(hooks.emit("after_skill_run", {"skill_id": request.skill_id, "finding_count": len(publishable_findings)}).id)

    mode = "DeepSeek v4 flash" if settings.use_real_llm else "规则引擎"
    return SkillRunResult(
        id=_run_id(),
        skill_id=request.skill_id,
        status="completed",
        summary=_summary(skill.name, mode, professional_context, publishable_findings, publishable_questions, request.clarification_answers, paused_for_confirmation),
        execution_steps=_execution_steps(request, mode, bool(professional_context.get("available")), publishable_findings, publishable_questions, paused_for_confirmation),
        final_answer=_final_answer(skill.name, publishable_findings, publishable_questions, bool(request.clarification_answers), paused_for_confirmation),
        findings=publishable_findings,
        hook_event_ids=event_ids,
        questions=publishable_questions,
        professional_references=professional_references,
    )


def _emit_before_run(request: SkillRunRequest):
    target_ids = set(request.policy_ids + request.process_ids + request.knowledge_node_ids)
    return hooks.emit(
        "before_skill_run",
        {
            "skill_id": request.skill_id,
            "target_ids": sorted(target_ids),
            "clarification_answer_count": len(request.clarification_answers),
        },
    )


def _load_professional_inputs(request: SkillRunRequest, context: dict) -> tuple[dict, list[ProfessionalReference], list[ClarificationQuestion]]:
    spec = get_skill_spec(request.skill_id)
    if not spec:
        return {}, [], []
    return load_professional_context(request, context, spec.definition.name)


def _analyze(
    request: SkillRunRequest,
    context: dict,
    professional_context: dict,
    professional_references: list[ProfessionalReference],
    questions: list[ClarificationQuestion],
    use_real_llm: bool,
) -> list[Finding]:
    if not use_real_llm:
        return run_rule_skill(request)
    findings, llm_questions = run_llm_skill(request, context, professional_context, professional_references)
    questions.extend(llm_questions)
    return findings


def _publish_findings(findings: list[Finding]) -> list[str]:
    event_ids = []
    for finding in findings:
        store.insert_finding(finding)
        created = hooks.emit("finding_created", {"finding_id": finding.id, "finding_type": finding.finding_type, "severity": finding.severity})
        event_ids.append(created.id)
        for evidence in finding.evidence:
            attached = hooks.emit("evidence_attached", {"finding_id": finding.id, "evidence_id": evidence.id, "source_type": evidence.source_type})
            event_ids.append(attached.id)
    return event_ids


def _attach_version_context(request: SkillRunRequest, findings: list[Finding]) -> list[Finding]:
    policies = {policy.id: policy.current_version_id for policy in store.all("policies") if policy.id in request.policy_ids}
    processes = {process.id: process.current_version_id for process in store.all("processes") if process.id in request.process_ids}
    for finding in findings:
        if not finding.policy_version_ids:
            finding.policy_version_ids = [version_id for version_id in policies.values() if version_id]
        if not finding.process_version_ids:
            finding.process_version_ids = [version_id for version_id in processes.values() if version_id]
    return findings


def _unanswered_questions(request: SkillRunRequest, questions: list[ClarificationQuestion]) -> list[ClarificationQuestion]:
    answered_keys = {key.strip() for key in request.clarification_answers}
    return [question for question in questions if question.question.strip() not in answered_keys and question.id.strip() not in answered_keys]


def _summary(
    skill_name: str,
    mode: str,
    professional_context: dict,
    findings: list[Finding],
    questions: list[ClarificationQuestion],
    clarification_answers: dict[str, str],
    paused_for_confirmation: bool,
) -> str:
    status = (
        f"{skill_name}已暂停，需先确认 {len(questions)} 个问题；确认前不输出风险结论。"
        if paused_for_confirmation
        else f"{skill_name}完成，{mode}生成 {len(findings)} 个待复核问题；"
    )
    return (
        status
        + f"专业知识库{'已参考' if professional_context.get('available') else '未可用'}，需确认问题 {len(questions)} 个"
        f"{'，已结合用户补充信息继续执行' if clarification_answers else ''}。"
    )


def _execution_steps(
    request: SkillRunRequest,
    settings_mode: str,
    professional_available: bool,
    findings: list[Finding],
    questions: list[ClarificationQuestion],
    paused_for_confirmation: bool = False,
) -> list[str]:
    steps = [
        f"读取当前输入资产：制度 {len(request.policy_ids)} 份，BPMN 流程 {len(request.process_ids)} 条。",
        f"查询专业知识库：{'已取得专业参考' if professional_available else '知识库不可用，保留人工确认问题'}。",
    ]
    if request.clarification_answers:
        steps.append(f"合并用户补充确认：{len(request.clarification_answers)} 条回答已作为本轮事实上下文。")
    steps.extend(
        [
            f"执行分析引擎：{settings_mode}。",
            "校验输出证据：只保留制度条款或 BPMN 节点能够支撑的问题。",
            f"二次验证风险结论：{len(findings)} 个问题已完成证据支撑性复核，其中 {sum(1 for finding in findings if finding.verification_status == 'uncertain')} 个标记为不确定。",
            (
                f"发现待确认项：{len(questions)} 个问题需要用户确认，已暂停输出风险结论。"
                if paused_for_confirmation
                else f"生成结果：{len(findings)} 个待复核问题，{len(questions)} 个待确认项。"
            ),
        ]
    )
    return steps


def _final_answer(
    skill_name: str,
    findings: list[Finding],
    questions: list[ClarificationQuestion],
    used_clarifications: bool,
    paused_for_confirmation: bool = False,
) -> str:
    prefix = f"已完成“{skill_name}”。"
    if used_clarifications:
        prefix += "本轮已结合你的补充回答重新判断。"
    if questions:
        if paused_for_confirmation:
            return f"“{skill_name}”需要先确认以下 {len(questions)} 个问题；确认前不会输出风险结论。"
        blocking_count = sum(1 for question in questions if question.blocking)
        return (
            f"{prefix} 当前还有 {len(questions)} 个需要人工确认的问题"
            f"{f'，其中 {blocking_count} 个会影响结论' if blocking_count else ''}。请在下方直接回复，我会带着你的回答继续执行。"
        )
    if findings:
        titles = "；".join(finding.title for finding in findings[:3])
        uncertain_count = sum(1 for finding in findings if finding.verification_status == "uncertain")
        uncertainty_text = f"其中 {uncertain_count} 个二次验证后仍不确定，已明确标注。" if uncertain_count else "所有问题已完成二次验证。"
        return f"{prefix} 本轮发现 {len(findings)} 个待复核问题：{titles}。{uncertainty_text}我已把证据和整改建议列在下方。"
    return f"{prefix} 本轮没有发现满足证据要求的风险问题。"
