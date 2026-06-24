from __future__ import annotations

import re
from uuid import uuid4

from app import db
from app.models import Evidence, Finding, PolicyClause, PolicyDocument, ProcessNode, SkillRunRequest


def run_rule_skill(request: SkillRunRequest) -> list[Finding]:
    if request.skill_id == "skill_policy_conflict":
        return _run_policy_conflict(request)
    if request.skill_id == "skill_policy_process_check":
        return _run_policy_process_check(request)
    if request.skill_id == "skill_no_policy_basis":
        return _run_no_policy_basis(request)
    return []


def _finding_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _thresholds(policy: PolicyDocument) -> list[tuple[int, str, PolicyClause]]:
    results: list[tuple[int, str, PolicyClause]] = []
    for clause in policy.clauses:
        for match in re.finditer(r"超过\s*(\d+)\s*万元", clause.content):
            threshold = int(match.group(1))
            role = _approval_role(clause.content)
            if role:
                results.append((threshold, role, clause))
    return results


def _approval_role(text: str) -> str | None:
    patterns = [
        r"提交([^，；。]+?)审批",
        r"由([^，；。]+?)审批",
        r"报([^，；。]+?)备案",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _policy_text(policies: list[PolicyDocument]) -> str:
    return "\n".join(clause.content for policy in policies for clause in policy.clauses)


def _policy_evidence(clause: PolicyClause, policy_name: str) -> Evidence:
    return Evidence(
        id=f"ev_{clause.id}",
        source_type="policy_clause",
        source_id=clause.id,
        label=f"{policy_name} {clause.clause_no}",
        quote=clause.content,
    )


def _node_evidence(node: ProcessNode, process_name: str) -> Evidence:
    return Evidence(
        id=f"ev_{node.id}",
        source_type="bpmn_node",
        source_id=node.id,
        label=f"{process_name} BPMN 节点",
        quote=f"{node.name}：{node.role}{node.action}。",
    )


def _run_policy_conflict(request: SkillRunRequest) -> list[Finding]:
    policies = db.selected_policies(request.policy_ids)
    findings: list[Finding] = []
    compared: set[tuple[str, str]] = set()
    for left in policies:
        for right in policies:
            if left.id == right.id or tuple(sorted([left.id, right.id])) in compared:
                continue
            compared.add(tuple(sorted([left.id, right.id])))
            for left_threshold, left_role, left_clause in _thresholds(left):
                for right_threshold, right_role, right_clause in _thresholds(right):
                    same_domain = (
                        left.category == right.category
                        or "采购" in left.name + left.category + right.name + right.category
                        or "招采" in left.name + left.category + right.name + right.category
                    )
                    if same_domain and (left_threshold != right_threshold or left_role != right_role):
                        findings.append(
                            Finding(
                                id=_finding_id("finding_conflict"),
                                finding_type="policy_conflict",
                                title="采购金额阈值或审批主体存在冲突",
                                description=(
                                    f"{left.name}规定超过{left_threshold}万元由{left_role}处理，"
                                    f"{right.name}规定超过{right_threshold}万元由{right_role}处理，"
                                    "二者适用范围存在重叠。"
                                ),
                                severity="high",
                                confidence=0.86,
                                skill_id=request.skill_id,
                                target_ids=[left.id, right.id],
                                evidence=[_policy_evidence(left_clause, left.name), _policy_evidence(right_clause, right.name)],
                                assumption="基于所选制度均适用于同一采购业务事项，且条款中的金额阈值和审批主体为当前有效要求。",
                                suggestion="建议明确平台制度与子公司细则的优先级，并统一重叠金额区间的审批主体和动作。",
                            )
                        )
                        break
                if findings and set(findings[-1].target_ids) == {left.id, right.id}:
                    break
    return findings


def _run_policy_process_check(request: SkillRunRequest) -> list[Finding]:
    policies = db.selected_policies(request.policy_ids)
    processes = db.selected_processes(request.process_ids)
    findings: list[Finding] = []
    text = _policy_text(policies)
    for process in processes:
        if "风控复核" in text and not any("风控" in node.name or "风控" in node.role for node in process.nodes):
            clause = next(clause for policy in policies for clause in policy.clauses if "风控复核" in clause.content)
            findings.append(
                Finding(
                    id=_finding_id("finding_missing_node"),
                    finding_type="missing_process_node",
                    title="采购流程缺少风控复核节点",
                    description="制度要求特定采购事项增加风控复核，但所选 BPMN 流程未配置对应节点。",
                    severity="medium",
                    confidence=0.82,
                    skill_id=request.skill_id,
                    target_ids=request.policy_ids + [process.id],
                    evidence=[
                        _policy_evidence(clause, next(policy.name for policy in policies if policy.id == clause.policy_id)),
                        Evidence(
                            id=f"ev_nodes_{process.id}",
                            source_type="bpmn_node",
                            source_id=process.id,
                            label=f"{process.name} BPMN 节点清单",
                            quote="、".join(node.name for node in process.nodes),
                        ),
                    ],
                    assumption="基于所选 BPMN 流程为该采购业务的实际审批配置，且所选制度条款为流程设计依据。",
                    suggestion="建议在总经理审批前增加“风控复核”节点，并设置金额或战略物资触发条件。",
                )
            )

        for node in process.nodes:
            if node.action != "审批":
                continue
            role_has_basis = node.role in text or node.name in text
            if not role_has_basis and ("董事长" in node.role or "董事长" in node.name):
                clause = next((clause for policy in policies for clause in policy.clauses if "总经理审批" in clause.content), None)
                evidence = [_node_evidence(node, process.name)]
                if clause:
                    policy_name = next(policy.name for policy in policies if policy.id == clause.policy_id)
                    evidence.insert(0, _policy_evidence(clause, policy_name))
                findings.append(
                    Finding(
                        id=_finding_id("finding_extra_node"),
                        finding_type="extra_process_node",
                        title="流程存在制度未要求的董事长审批节点",
                        description=f"{process.name}包含“{node.name}”，但所选制度中未找到该审批主体的明确依据。",
                        severity="medium",
                        confidence=0.76,
                        skill_id=request.skill_id,
                        target_ids=request.policy_ids + [process.id],
                        evidence=evidence,
                        assumption="基于所选制度范围内未发现董事长审批主体的直接授权条款，且当前流程节点属于业务审批节点而非技术流转节点。",
                        suggestion="建议确认是否存在其他授权文件；如无，应删除该节点或补充制度依据。",
                    )
                )
    findings.extend(_run_no_policy_basis(request, skill_id="skill_policy_process_check"))
    return _dedupe_findings(findings)


def _run_no_policy_basis(request: SkillRunRequest, skill_id: str | None = None) -> list[Finding]:
    policies = db.selected_policies(request.policy_ids) if request.policy_ids else db.all_policies()
    processes = db.selected_processes(request.process_ids)
    text = _policy_text(policies)
    findings: list[Finding] = []
    for process in processes:
        for node in process.nodes:
            if node.action == "提交":
                continue
            has_basis = node.name in text or node.role in text
            if "定薪" in node.name and "定薪审批" not in text:
                has_basis = False
            if not has_basis:
                supporting_clause = next((clause for policy in policies for clause in policy.clauses if "薪酬定级" in clause.content), None)
                evidence = [_node_evidence(node, process.name)]
                if supporting_clause:
                    policy_name = next(policy.name for policy in policies if policy.id == supporting_clause.policy_id)
                    evidence.append(_policy_evidence(supporting_clause, policy_name))
                findings.append(
                    Finding(
                        id=_finding_id("finding_no_basis"),
                        finding_type="no_policy_basis",
                        title=f"{node.name}节点疑似缺少制度依据",
                        description=f"{process.name}包含“{node.name}”，但所选制度范围内未找到可直接支撑该节点的条款。",
                        severity="high" if "定薪" in node.name else "medium",
                        confidence=0.82,
                        skill_id=skill_id or request.skill_id,
                        target_ids=request.process_ids + request.policy_ids,
                        evidence=evidence,
                        assumption="基于当前所选制度范围作为依据全集，且该流程节点属于需要制度授权的审批/审核/备案类节点。",
                        suggestion="建议补充对应制度条款，或将该审批动作拆分到有明确依据的独立流程。",
                    )
                )
    return findings


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    deduped: list[Finding] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for finding in findings:
        key = (finding.finding_type, finding.title, tuple(sorted(evidence.source_id for evidence in finding.evidence)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped
