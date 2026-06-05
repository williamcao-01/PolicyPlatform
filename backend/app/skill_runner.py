from __future__ import annotations

import re
import json
from uuid import uuid4

from app import db
from app.deepseek_client import DeepSeekClient, load_deepseek_settings
from app.hooks import hooks
from app.knowledge_base import (
    KnowledgeBaseClient,
    build_skill_kb_question,
    clarification_questions_from_kb,
    professional_references_from_kb,
)
from app.models import (
    ClarificationQuestion,
    Evidence,
    Finding,
    PolicyClause,
    PolicyDocument,
    ProcessDefinition,
    ProcessNode,
    ProfessionalReference,
    SkillRunRequest,
    SkillRunResult,
)
from app.skill_registry import get_skill_spec
from app.store import store


def _run_id() -> str:
    return f"run_{uuid4().hex[:10]}"


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
    return findings


def _run_no_policy_basis(request: SkillRunRequest) -> list[Finding]:
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
                        skill_id=request.skill_id,
                        target_ids=request.process_ids + request.policy_ids,
                        evidence=evidence,
                        assumption="基于当前所选制度范围作为依据全集，且该流程节点属于需要制度授权的审批/审核/备案类节点。",
                        suggestion="建议补充对应制度条款，或将该审批动作拆分到有明确依据的独立流程。",
                    )
                )
    return findings


def _context_payload(request: SkillRunRequest) -> dict:
    policies = db.selected_policies(request.policy_ids) if request.policy_ids else db.all_policies()
    processes = db.selected_processes(request.process_ids)
    return {
        "policies": [
            {
                "id": policy.id,
                "name": policy.name,
                "category": policy.category,
                "clauses": [
                    {
                        "id": clause.id,
                        "clause_no": clause.clause_no,
                        "title": clause.title,
                        "content": clause.content,
                    }
                    for clause in policy.clauses
                ],
            }
            for policy in policies
        ],
        "processes": [
            {
                "id": process.id,
                "name": process.name,
                "nodes": [
                    {
                        "id": node.id,
                        "bpmn_element_id": node.bpmn_element_id,
                        "name": node.name,
                        "role": node.role,
                        "action": node.action,
                        "condition": node.condition,
                        "order_index": node.order_index,
                    }
                    for node in process.nodes
                ],
            }
            for process in processes
        ],
    }


def _professional_context(request: SkillRunRequest, context: dict, spec_name: str) -> tuple[dict, list[ProfessionalReference], list[ClarificationQuestion]]:
    policy_names = [policy["name"] for policy in context["policies"]]
    process_names = [process["name"] for process in context["processes"]]
    question = build_skill_kb_question(request.skill_id, spec_name, policy_names, process_names)
    compact_context = json.dumps(
        {
            "policies": [{"name": item["name"], "category": item["category"]} for item in context["policies"]],
            "processes": [{"name": item["name"], "nodes": [node["name"] for node in item["nodes"]]} for item in context["processes"]],
        },
        ensure_ascii=False,
    )
    data = KnowledgeBaseClient().ask(question=question, context=compact_context, limit=6)
    return data, professional_references_from_kb(data), clarification_questions_from_kb(data)


def _llm_questions(raw_questions: list, existing_count: int) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    for index, item in enumerate(raw_questions[:8]):
        if isinstance(item, str):
            text = item
            reason = "模型认为该事实会影响专业判断。"
            blocking = False
        elif isinstance(item, dict):
            text = str(item.get("question") or item.get("text") or "").strip()
            reason = str(item.get("reason") or "模型认为该事实会影响专业判断。")
            blocking = bool(item.get("blocking", False))
        else:
            continue
        if not text:
            continue
        if not _is_valid_clarification_question(text, reason):
            continue
        questions.append(
            ClarificationQuestion(
                id=f"llmq_{existing_count + index + 1}",
                question=text,
                reason=reason,
                blocking=blocking,
                source="llm",
            )
        )
    return questions


def _is_valid_clarification_question(text: str, reason: str) -> bool:
    action_recommendation_patterns = [
        r"是否(需要|应当|要)?(新增|增加|添加|补充|删除|移除|调整|修改|更改|优化|完善)",
        r"是否(同意|允许|确认).*?(新增|增加|添加|补充|删除|移除|调整|修改|更改|优化|完善)",
        r"(添加|补充|修改|更改|调整).*(制度条款|流程节点|节点名称|审批节点)",
    ]
    if any(re.search(pattern, text + reason) for pattern in action_recommendation_patterns):
        return False
    clarification_keywords = [
        "同一含义",
        "等同",
        "相同",
        "是否指",
        "是否为同一",
        "适用范围",
        "版本",
        "生效",
        "所选制度范围",
        "缺失",
        "未提供",
        "引用文件",
        "语义",
        "术语",
        "角色",
        "组织",
        "边界",
    ]
    return any(keyword in text + reason for keyword in clarification_keywords)


def _run_llm_skill(
    request: SkillRunRequest,
    professional_context: dict,
    professional_references: list[ProfessionalReference],
) -> tuple[list[Finding], list[ClarificationQuestion]]:
    spec = get_skill_spec(request.skill_id)
    if not spec:
        return [], []
    context = _context_payload(request)
    evidence_index: dict[str, tuple[str, str, str]] = {}
    for policy in context["policies"]:
        for clause in policy["clauses"]:
            evidence_index[clause["id"]] = ("policy_clause", f"{policy['name']} {clause['clause_no']}", clause["content"])
    for process in context["processes"]:
        for node in process["nodes"]:
            evidence_index[node["id"]] = ("bpmn_node", f"{process['name']} BPMN 节点", f"{node['name']}：{node['role']}{node['action']}。")

    schema = spec.schema
    allowed_types = schema.get("allowed_finding_types", [])
    evidence_policy = schema.get("evidence_policy", {})
    min_evidence = int(evidence_policy.get("min_evidence", 1))
    allowed_source_types = set(evidence_policy.get("allowed_source_types", ["policy_clause", "bpmn_node"]))
    system_prompt = (
        f"{spec.prompt}\n\n"
        "你必须综合专业知识库返回的专业意见，但风险finding必须只用用户提供的制度条款和BPMN流程节点作为证据。"
        "知识库只用于专业判断框架、术语边界、治理建议和不确定性识别，不得作为finding的evidence_id。"
        "输出必须是JSON对象，格式为："
        "{\"findings\":[{\"finding_type\":\"policy_conflict|missing_process_node|extra_process_node|authority_mismatch|no_policy_basis\","
        "\"title\":\"...\",\"description\":\"...\",\"severity\":\"low|medium|high|critical\",\"confidence\":0.0,"
        "\"evidence_ids\":[\"制度条款id或流程节点id\"],\"assumption\":\"判断成立所依赖的事实或语义假设\",\"suggestion\":\"...\"}],"
        "\"questions\":[{\"question\":\"需要用户确认的问题\",\"reason\":\"为什么需要确认\",\"blocking\":false}]}"
        f"允许的finding_type为：{allowed_types}。"
        f"每个finding至少包含{min_evidence}个evidence_id；evidence_id必须来自输入。"
        "questions只用于会改变判断结论的事实不确定性，例如相似术语是否同义、角色名称是否同一主体、制度版本或适用范围是否覆盖当前对象、引用文件是否属于本次证据范围。"
        "不要把“是否新增制度条款、是否修改流程节点、是否补充控制点、是否更改节点名称”等整改动作写入questions；这些应作为finding的suggestion或description输出。"
        "每个finding必须覆盖风险描述、原文依据、判断假设、优化建议四类信息，其中原文依据通过evidence_ids给出，判断假设写入assumption。"
    )
    user_prompt = json.dumps(
        {
            "skill_id": request.skill_id,
            "skill_name": spec.definition.name,
            "skill_guide": spec.guide,
            "context": context,
            "user_clarification_answers": request.clarification_answers,
            "professional_knowledge_base": {
                "available": professional_context.get("available", False),
                "answer": professional_context.get("answer", ""),
                "references": professional_context.get("references", []),
                "related_concepts": professional_context.get("related_concepts", []),
                "knowledge_gaps": professional_context.get("knowledge_gaps", []),
                "confidence": professional_context.get("confidence"),
            },
            "quality_requirements": [
                "优先少而准，避免泛泛而谈。",
                "没有明确证据就不要输出finding。",
                "标题要能直接作为风险清单标题。",
                "建议要能指导制度或流程整改。",
                "有不确定事实就输出questions，不要用猜测替代用户确认。",
                "已能基于当前制度和BPMN证据判断的问题必须输出finding，不要改成让用户确认。",
                "整改动作、补条款、改节点、改名称属于优化建议，不属于待确认问题。",
                "finding输出必须包含description、evidence_ids、assumption、suggestion。",
                "如果用户已回答clarification问题，必须基于回答继续判断；已被回答的问题不要重复提出，除非回答仍不充分。",
            ],
        },
        ensure_ascii=False,
    )
    before_llm = hooks.emit("before_llm_call", {"skill_id": request.skill_id, "model": load_deepseek_settings().model})
    raw = DeepSeekClient().chat_json(system_prompt, user_prompt)
    hooks.emit("after_llm_call", {"skill_id": request.skill_id, "hook_id": before_llm.id, "finding_count": len(raw.get("findings", []))})

    findings: list[Finding] = []
    questions = _llm_questions(raw.get("questions", []), 0)
    for item in raw.get("findings", []):
        evidences: list[Evidence] = []
        for evidence_id in item.get("evidence_ids", []):
            if evidence_id not in evidence_index:
                continue
            source_type, label, quote = evidence_index[evidence_id]
            if source_type not in allowed_source_types:
                continue
            evidences.append(Evidence(id=f"ev_{evidence_id}", source_type=source_type, source_id=evidence_id, label=label, quote=quote))
        if len(evidences) < min_evidence:
            hooks.emit("llm_finding_rejected", {"skill_id": request.skill_id, "reason": "insufficient_valid_evidence", "title": item.get("title")})
            continue
        finding_type = item.get("finding_type", allowed_types[0] if allowed_types else "policy_conflict")
        if allowed_types and finding_type not in allowed_types:
            hooks.emit("llm_finding_rejected", {"skill_id": request.skill_id, "reason": "invalid_finding_type", "title": item.get("title"), "finding_type": finding_type})
            continue
        findings.append(
            Finding(
                id=_finding_id("finding_llm"),
                finding_type=finding_type,
                title=item.get("title", "未命名风险"),
                description=item.get("description", ""),
                severity=item.get("severity", "medium"),
                confidence=float(item.get("confidence", 0.7)),
                skill_id=request.skill_id,
                target_ids=request.policy_ids + request.process_ids,
                evidence=evidences,
                assumption=str(item.get("assumption") or "基于当前所选制度条款和 BPMN 节点作为本次核验的有效证据范围。"),
                suggestion=item.get("suggestion", ""),
                professional_references=professional_references,
            )
        )
    return findings, questions


def _unanswered_questions(request: SkillRunRequest, questions: list[ClarificationQuestion]) -> list[ClarificationQuestion]:
    answered_keys = {key.strip() for key in request.clarification_answers}
    return [question for question in questions if question.question.strip() not in answered_keys and question.id.strip() not in answered_keys]


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
        return f"{prefix} 本轮发现 {len(findings)} 个待复核问题：{titles}。我已把证据和整改建议列在下方。"
    return f"{prefix} 本轮没有发现满足证据要求的风险问题。"


def run_skill(request: SkillRunRequest) -> SkillRunResult:
    skill = store.get_skill(request.skill_id)
    if not skill:
        event = hooks.emit("skill_run_failed", {"skill_id": request.skill_id, "reason": "unknown_skill"})
        return SkillRunResult(id=_run_id(), skill_id=request.skill_id, status="failed", summary="未找到对应 Skill。", findings=[], hook_event_ids=[event.id])

    target_ids = set(request.policy_ids + request.process_ids + request.knowledge_node_ids)
    before = hooks.emit(
        "before_skill_run",
        {
            "skill_id": request.skill_id,
            "target_ids": sorted(target_ids),
            "clarification_answer_count": len(request.clarification_answers),
        },
    )
    spec = get_skill_spec(request.skill_id)
    context = _context_payload(request)
    professional_context: dict = {}
    professional_references: list[ProfessionalReference] = []
    questions: list[ClarificationQuestion] = []
    if spec:
        professional_context, professional_references, questions = _professional_context(request, context, spec.definition.name)

    settings = load_deepseek_settings()
    if settings.use_real_llm:
        findings, llm_questions = _run_llm_skill(request, professional_context, professional_references)
        questions.extend(llm_questions)
    else:
        if request.skill_id == "skill_policy_conflict":
            findings = _run_policy_conflict(request)
        elif request.skill_id == "skill_policy_process_check":
            findings = _run_policy_process_check(request)
        elif request.skill_id == "skill_no_policy_basis":
            findings = _run_no_policy_basis(request)
        else:
            findings = []

    unanswered = _unanswered_questions(request, questions)
    paused_for_confirmation = bool(unanswered)
    publishable_findings = [] if paused_for_confirmation else findings
    publishable_questions = unanswered if paused_for_confirmation else unanswered

    event_ids = [before.id]
    for finding in publishable_findings:
        store.insert_finding(finding)
        created = hooks.emit("finding_created", {"finding_id": finding.id, "finding_type": finding.finding_type, "severity": finding.severity})
        event_ids.append(created.id)
        for evidence in finding.evidence:
            attached = hooks.emit("evidence_attached", {"finding_id": finding.id, "evidence_id": evidence.id, "source_type": evidence.source_type})
            event_ids.append(attached.id)

    after = hooks.emit("after_skill_run", {"skill_id": request.skill_id, "finding_count": len(publishable_findings)})
    event_ids.append(after.id)

    return SkillRunResult(
        id=_run_id(),
        skill_id=request.skill_id,
        status="completed",
        summary=(
            (
                f"{skill.name}已暂停，需先确认 {len(publishable_questions)} 个问题；确认前不输出风险结论。"
                if paused_for_confirmation
                else f"{skill.name}完成，{'DeepSeek v4 flash' if settings.use_real_llm else '规则引擎'}生成 {len(publishable_findings)} 个待复核问题；"
            )
            + f"专业知识库{'已参考' if professional_context.get('available') else '未可用'}，需确认问题 {len(publishable_questions)} 个"
            f"{'，已结合用户补充信息继续执行' if request.clarification_answers else ''}。"
        ),
        execution_steps=_execution_steps(
            request,
            "DeepSeek v4 flash" if settings.use_real_llm else "规则引擎",
            bool(professional_context.get("available")),
            publishable_findings,
            publishable_questions,
            paused_for_confirmation,
        ),
        final_answer=_final_answer(skill.name, publishable_findings, publishable_questions, bool(request.clarification_answers), paused_for_confirmation),
        findings=publishable_findings,
        hook_event_ids=event_ids,
        questions=publishable_questions,
        professional_references=professional_references,
    )
