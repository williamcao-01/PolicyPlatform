from __future__ import annotations

import json

from app.deepseek_client import DeepSeekClient
from app.hooks import hooks
from app.models import Finding, SkillRunRequest


def verify_findings(request: SkillRunRequest, context: dict, findings: list[Finding], use_real_llm: bool) -> list[Finding]:
    if not findings:
        return findings

    evidence_index = _build_evidence_index(context)
    deterministic_results = [_verify_evidence_integrity(finding, evidence_index) for finding in findings]
    verified_findings = [
        _mark_uncertain(finding, note) if note else finding.model_copy(update={"verification_status": "verified", "verification_note": "已完成证据完整性校验。"})
        for finding, note in zip(findings, deterministic_results, strict=True)
    ]

    if not use_real_llm:
        _emit_verification_hook(request, verified_findings)
        return verified_findings

    try:
        model_results = _llm_verify_findings(verified_findings)
    except Exception as exc:
        hooks.emit("finding_verification_failed", {"skill_id": request.skill_id, "reason": str(exc)})
        uncertain = [_mark_uncertain(finding, "二次验证模型调用失败，无法确认该风险结论是否被证据充分支撑。") for finding in verified_findings]
        _emit_verification_hook(request, uncertain)
        return uncertain

    result_by_id = {str(item.get("id")): item for item in model_results}
    next_findings = []
    for finding in verified_findings:
        if finding.verification_status == "uncertain":
            next_findings.append(finding)
            continue
        item = result_by_id.get(finding.id)
        if not item:
            next_findings.append(_mark_uncertain(finding, "二次验证未返回该风险点的验证结果。"))
            continue
        status = str(item.get("verification_status") or "").strip()
        note = str(item.get("verification_note") or "").strip()
        if status != "verified":
            next_findings.append(_mark_uncertain(finding, note or "二次验证认为现有证据不足以确认该风险结论。"))
        else:
            next_findings.append(finding.model_copy(update={"verification_status": "verified", "verification_note": note or "二次验证确认该风险结论被现有证据支撑。"}))
    _emit_verification_hook(request, next_findings)
    return next_findings


def _build_evidence_index(context: dict) -> dict[str, tuple[str, str]]:
    evidence_index: dict[str, tuple[str, str]] = {}
    for policy in context["policies"]:
        for clause in policy["clauses"]:
            evidence_index[clause["id"]] = ("policy_clause", clause["content"])
    for process in context["processes"]:
        for node in process["nodes"]:
            evidence_index[node["id"]] = ("bpmn_node", f"{node['name']}：{node['role']}{node['action']}。")
        evidence_index[process["id"]] = ("bpmn_node", "、".join(node["name"] for node in process["nodes"]))
    return evidence_index


def _verify_evidence_integrity(finding: Finding, evidence_index: dict[str, tuple[str, str]]) -> str:
    if not finding.evidence:
        return "该风险点没有绑定制度条款或 BPMN 节点证据，不能作为确定风险输出。"
    for evidence in finding.evidence:
        indexed = evidence_index.get(evidence.source_id)
        if not indexed:
            return f"证据 {evidence.label} 未在本次输入资产中找到。"
        source_type, source_quote = indexed
        if source_type != evidence.source_type:
            return f"证据 {evidence.label} 的来源类型与输入资产不一致。"
        if evidence.quote and evidence.quote not in source_quote and source_quote not in evidence.quote:
            return f"证据 {evidence.label} 的引用内容与输入资产原文不一致。"
    return ""


def _llm_verify_findings(findings: list[Finding]) -> list[dict]:
    payload = [
        {
            "id": finding.id,
            "title": finding.title,
            "description": finding.description,
            "assumption": finding.assumption,
            "suggestion": finding.suggestion,
            "evidence": [evidence.model_dump() for evidence in finding.evidence],
        }
        for finding in findings
        if finding.verification_status == "verified"
    ]
    system_prompt = (
        "你是制度与流程风险结论的二次验证员。"
        "只能根据每个风险点附带的 evidence 判断该风险结论是否被证据直接支撑。"
        "不要引入外部知识，不要补充想象事实。"
        "如果证据只能说明可能存在问题、需要额外制度/流程/业务事实确认，必须标记为 uncertain。"
        "输出JSON对象：{\"results\":[{\"id\":\"...\",\"verification_status\":\"verified|uncertain\",\"verification_note\":\"...\"}]}。"
    )
    user_prompt = json.dumps({"findings": payload}, ensure_ascii=False)
    raw = DeepSeekClient().chat_json(system_prompt, user_prompt)
    results = raw.get("results", [])
    return results if isinstance(results, list) else []


def _mark_uncertain(finding: Finding, note: str) -> Finding:
    return finding.model_copy(
        update={
            "verification_status": "uncertain",
            "verification_note": note,
            "confidence": min(finding.confidence, 0.55),
        }
    )


def _emit_verification_hook(request: SkillRunRequest, findings: list[Finding]) -> None:
    hooks.emit(
        "findings_verified",
        {
            "skill_id": request.skill_id,
            "finding_count": len(findings),
            "uncertain_count": sum(1 for finding in findings if finding.verification_status == "uncertain"),
        },
    )
