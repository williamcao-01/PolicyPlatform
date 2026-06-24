from __future__ import annotations

import json
import re
from uuid import uuid4

from app.deepseek_client import DeepSeekClient, load_deepseek_settings
from app.hooks import hooks
from app.models import ClarificationQuestion, Evidence, Finding, ProfessionalReference, SkillRunRequest
from app.skill_registry import get_skill_spec


def run_llm_skill(
    request: SkillRunRequest,
    context: dict,
    professional_context: dict,
    professional_references: list[ProfessionalReference],
) -> tuple[list[Finding], list[ClarificationQuestion]]:
    spec = get_skill_spec(request.skill_id)
    if not spec:
        return [], []

    evidence_index = _build_evidence_index(context)
    allowed_types, min_evidence, allowed_source_types = _evidence_contract(spec.schema)
    before_llm = hooks.emit("before_llm_call", {"skill_id": request.skill_id, "model": load_deepseek_settings().model})
    raw = DeepSeekClient().chat_json(
        _system_prompt(spec.prompt, allowed_types, min_evidence),
        _user_prompt(request, context, spec.definition.name, spec.guide, professional_context),
    )
    hooks.emit("after_llm_call", {"skill_id": request.skill_id, "hook_id": before_llm.id, "finding_count": len(raw.get("findings", []))})

    findings = _findings_from_llm(
        raw.get("findings", []),
        request,
        evidence_index,
        allowed_types,
        min_evidence,
        allowed_source_types,
        professional_references,
    )
    return findings, _llm_questions(raw.get("questions", []), 0)


def _build_evidence_index(context: dict) -> dict[str, tuple[str, str, str]]:
    evidence_index: dict[str, tuple[str, str, str]] = {}
    for policy in context["policies"]:
        for clause in policy["clauses"]:
            evidence_index[clause["id"]] = ("policy_clause", f"{policy['name']} {clause['clause_no']}", clause["content"])
    for process in context["processes"]:
        for node in process["nodes"]:
            evidence_index[node["id"]] = ("bpmn_node", f"{process['name']} BPMN 节点", f"{node['name']}：{node['role']}{node['action']}。")
    return evidence_index


def _evidence_contract(schema: dict) -> tuple[list[str], int, set[str]]:
    allowed_types = schema.get("allowed_finding_types", [])
    evidence_policy = schema.get("evidence_policy", {})
    min_evidence = int(evidence_policy.get("min_evidence", 1))
    allowed_source_types = set(evidence_policy.get("allowed_source_types", ["policy_clause", "bpmn_node"]))
    return allowed_types, min_evidence, allowed_source_types


def _system_prompt(skill_prompt: str, allowed_types: list[str], min_evidence: int) -> str:
    return (
        f"{skill_prompt}\n\n"
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


def _user_prompt(request: SkillRunRequest, context: dict, skill_name: str, skill_guide: str, professional_context: dict) -> str:
    return json.dumps(
        {
            "skill_id": request.skill_id,
            "skill_name": skill_name,
            "skill_guide": skill_guide,
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


def _findings_from_llm(
    raw_findings: list,
    request: SkillRunRequest,
    evidence_index: dict[str, tuple[str, str, str]],
    allowed_types: list[str],
    min_evidence: int,
    allowed_source_types: set[str],
    professional_references: list[ProfessionalReference],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in raw_findings:
        evidences = _valid_evidences(item.get("evidence_ids", []), evidence_index, allowed_source_types)
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
    return findings


def _valid_evidences(evidence_ids: list, evidence_index: dict[str, tuple[str, str, str]], allowed_source_types: set[str]) -> list[Evidence]:
    evidences: list[Evidence] = []
    for evidence_id in evidence_ids:
        if evidence_id not in evidence_index:
            continue
        source_type, label, quote = evidence_index[evidence_id]
        if source_type not in allowed_source_types:
            continue
        evidences.append(Evidence(id=f"ev_{evidence_id}", source_type=source_type, source_id=evidence_id, label=label, quote=quote))
    return evidences


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
        if not text or not _is_valid_clarification_question(text, reason):
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


def _finding_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"

