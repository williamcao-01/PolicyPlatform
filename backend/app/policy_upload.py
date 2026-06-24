from __future__ import annotations

import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app import db
from app.deepseek_client import DeepSeekClient, load_deepseek_settings
from app.hooks import hooks
from app.knowledge_base import (
    KnowledgeBaseClient,
    build_skill_kb_question,
    clarification_questions_from_kb,
    professional_references_from_kb,
)
from app.models import PolicyClause, PolicyDocument
from app.policy_upload_admission import normalize_upload_admission
from app.policy_upload_parser import (
    extract_policy_concepts,
    extract_policy_metadata,
    extract_upload_text,
    extract_upload_text_from_bytes,
    filter_policy_concepts,
    safe_upload_id,
    split_policy_clauses,
)
from app.skill_registry import get_skill_spec


def _heuristic_analysis(text: str, file_name: str) -> dict[str, Any]:
    metadata = extract_policy_metadata(text)
    temp_policy_id = safe_upload_id("policy", metadata["name"])
    clauses = split_policy_clauses(text, temp_policy_id)
    has_structure = len(clauses) >= 3
    has_policy_name = metadata["name"] != "未命名制度"
    has_scope_or_purpose = "目的" in text or "适用范围" in text
    suitable = has_structure and has_policy_name and has_scope_or_purpose
    reasons = []
    suggestions = []
    questions = []
    if not has_policy_name:
        reasons.append("未识别到清晰的制度名称。")
        questions.append("请确认制度名称。")
    if not has_structure:
        reasons.append("未识别到足够的章节条款结构。")
        suggestions.append("建议补充按 1、1.1、1.1.1 等编号组织的条款。")
    if not has_scope_or_purpose:
        reasons.append("未识别到目的或适用范围。")
        questions.append("请补充制度目的或适用范围。")
    if not metadata["code"]:
        questions.append("请确认制度编号。")
    if not metadata["version"]:
        questions.append("请确认制度版本。")
    if not metadata["effective_date"]:
        questions.append("请确认制度生效日期。")
    analysis = {
        "analysis_id": "",
        "file_name": file_name,
        "suitable": suitable,
        "reasons": reasons,
        "suggestions": suggestions,
        "questions": questions,
        "metadata": metadata,
        "clauses": clauses,
        "concepts": extract_policy_concepts(text),
        "professional_references": [],
        "professional_questions": [],
        "text_preview": text[:1200],
    }
    return normalize_upload_admission(analysis, text, metadata, clauses)


def _llm_analysis(text: str, file_name: str) -> dict[str, Any]:
    spec = get_skill_spec("skill_upload_policy_file")
    kb_question = build_skill_kb_question("skill_upload_policy_file", "上传制度文件", [], [])
    kb_context = json.dumps({"file_name": file_name, "text_preview": text[:3000]}, ensure_ascii=False)
    kb_data = KnowledgeBaseClient().ask(kb_question, context=kb_context, limit=6)
    professional_references = [item.model_dump() for item in professional_references_from_kb(kb_data)]
    professional_questions = [item.model_dump() for item in clarification_questions_from_kb(kb_data)]
    if not spec or not load_deepseek_settings().use_real_llm:
        analysis = _heuristic_analysis(text, file_name)
        analysis["professional_references"] = professional_references
        analysis["professional_questions"] = professional_questions
        return analysis

    hooks.emit("before_llm_call", {"skill_id": "skill_upload_policy_file", "model": load_deepseek_settings().model})
    try:
        result = DeepSeekClient().chat_json(_upload_system_prompt(spec.prompt), _upload_user_prompt(text, file_name, kb_data))
        hooks.emit("after_llm_call", {"skill_id": "skill_upload_policy_file", "finding_count": 0})
    except Exception as exc:
        hooks.emit("upload_analysis_fallback", {"reason": str(exc)})
        analysis = _heuristic_analysis(text, file_name)
        analysis["professional_references"] = professional_references
        analysis["professional_questions"] = professional_questions
        return analysis

    fallback = _heuristic_analysis(text, file_name)
    metadata = {**fallback["metadata"], **result.get("metadata", {})}
    policy_id = safe_upload_id("policy", metadata.get("name") or file_name)
    clauses = _rebuild_clauses_for_policy(policy_id, fallback["clauses"])
    analysis = {
        "analysis_id": "",
        "file_name": file_name,
        "suitable": bool(result.get("suitable", fallback["suitable"])),
        "reasons": result.get("reasons", fallback["reasons"]),
        "suggestions": result.get("suggestions", fallback["suggestions"]),
        "questions": result.get("questions", fallback["questions"]),
        "metadata": metadata,
        "clauses": clauses,
        "concepts": filter_policy_concepts(result.get("concepts", fallback["concepts"])),
        "professional_references": professional_references,
        "professional_questions": professional_questions,
        "text_preview": text[:1200],
    }
    return normalize_upload_admission(analysis, text, metadata, clauses)


def _upload_system_prompt(skill_prompt: str) -> str:
    return (
        f"{skill_prompt}\n\n"
        "你必须综合专业知识库返回的专业意见，用于判断制度框架、条款结构、治理要素、流程和合规控制是否完整。"
        "知识库只作为专业参考，不能替代用户上传文件中的事实。"
        "输出JSON对象，字段为：suitable(boolean), reasons(string[]), suggestions(string[]), "
        "questions(string[]), metadata(object), clauses(array), concepts(array)。"
        "metadata字段包含name, code, version, effective_date, category, org_scope。"
        "clauses字段每项包含clause_no,title,content。concepts每项包含node_type,name。"
        "concepts的node_type只能是人员角色、业务规则、部门组织三类。"
        "questions只用于入库必需事实缺失或语义边界会影响保存位置、元数据或角色抽取的问题，"
        "例如制度名称/编号/版本/生效日期无法判断、保存结构项不明确、相似组织/角色是否同一主体、引用文件是否属于本次入库范围。"
        "角色未定义、术语未定义、缺少监督检查/违规追责章节、引用文件状态不明等细节完善项默认写入suggestions，不要强制逐条确认。"
    )


def _upload_user_prompt(text: str, file_name: str, kb_data: dict[str, Any]) -> str:
    return json.dumps(
        {
            "file_name": file_name,
            "text": text[:18000],
            "professional_knowledge_base": {
                "available": kb_data.get("available", False),
                "answer": kb_data.get("answer", ""),
                "references": kb_data.get("references", []),
                "related_concepts": kb_data.get("related_concepts", []),
                "knowledge_gaps": kb_data.get("knowledge_gaps", []),
                "confidence": kb_data.get("confidence"),
            },
        },
        ensure_ascii=False,
    )


def _rebuild_clauses_for_policy(policy_id: str, raw_clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scoped_raw_clauses = raw_clauses[:160]
    id_map = {item.get("id"): f"clause_{policy_id}_{idx + 1}" for idx, item in enumerate(scoped_raw_clauses)}
    clauses = []
    for idx, item in enumerate(scoped_raw_clauses):
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        clauses.append(
            {
                "id": id_map.get(item.get("id"), f"clause_{policy_id}_{idx + 1}"),
                "policy_id": policy_id,
                "clause_no": str(item.get("clause_no") or idx + 1),
                "title": str(item.get("title") or f"条款 {idx + 1}")[:80],
                "content": content,
                "parent_id": id_map.get(item.get("parent_id")),
                "order_index": idx + 1,
            }
        )
    return clauses


def analyze_policy_text(text: str, file_name: str, source_bytes: bytes | None = None, content_type: str = "application/octet-stream") -> dict[str, Any]:
    analysis = _llm_analysis(text, file_name)
    analysis_id = safe_upload_id("upload", file_name)
    analysis["analysis_id"] = analysis_id
    _attach_version_match(analysis)
    if source_bytes is not None:
        analysis["source_file"] = _save_source_file(analysis_id, file_name, source_bytes, content_type)
    db.insert_upload_session(analysis_id, analysis)
    return analysis


def save_policy_analysis(analysis_id: str, category: str, answers: dict[str, str]) -> PolicyDocument:
    analysis = db.get_upload_session(analysis_id)
    if not analysis:
        raise ValueError("Upload analysis not found.")
    if not analysis.get("suitable"):
        raise ValueError("当前分析结果不适合入库，请先修改文件后重新上传。")
    if not category.strip():
        raise ValueError("请先选择要保存到制度树中的哪个结构项。")
    metadata = analysis["metadata"]
    version_match = analysis.get("version_match") or {}
    matched_policy = _resolve_version_target(version_match, answers)
    policy_id = matched_policy.id if matched_policy else safe_upload_id("policy", metadata.get("name") or analysis["file_name"])
    raw_clauses = analysis.get("clauses", [])
    id_map = {clause.get("id"): f"clause_{policy_id}_{idx + 1}" for idx, clause in enumerate(raw_clauses)}
    clauses = [
        PolicyClause.model_validate(
            {
                **clause,
                "policy_id": policy_id,
                "id": id_map.get(clause.get("id"), f"clause_{policy_id}_{idx + 1}"),
                "parent_id": id_map.get(clause.get("parent_id")),
            }
        )
        for idx, clause in enumerate(raw_clauses)
    ]
    existing_versions = db.fetch_policy_versions(policy_id) if matched_policy else []
    generated_version = f"v{len(existing_versions) + 1}" if matched_policy else "v1"
    policy = PolicyDocument(
        id=policy_id,
        name=_field_value("name", answers, metadata, matched_policy.name if matched_policy else analysis["file_name"]),
        code=_field_value("code", answers, metadata, matched_policy.code if matched_policy else "待确认"),
        version=answers.get("version") or metadata.get("version") or generated_version,
        category=category or metadata.get("category") or "未分类",
        org_scope=_field_value("org_scope", answers, metadata, matched_policy.org_scope if matched_policy else "待确认"),
        status="effective",
        effective_date=answers.get("effective_date") or metadata.get("effective_date") or "待确认",
        clauses=clauses,
        source_file=analysis.get("source_file"),
    )
    version = db.insert_current_policy_version(
        policy,
        change_summary="上传制度文件后保存为默认生效新版本" if matched_policy else "上传制度文件后保存为初始版本",
    )
    hooks.emit(
        "policy_upload_saved",
        {
            "analysis_id": analysis_id,
            "policy_id": policy.id,
            "version_id": version.id,
            "version_no": version.version_no,
            "saved_as": "new_version" if matched_policy else "new_policy",
            "category": policy.category,
            "clause_count": len(policy.clauses),
            "role_candidate_count": len(analysis.get("concepts", [])),
            "clarification_answer_count": len(answers),
            "clarification_answers": answers,
        },
    )
    return policy


def _attach_version_match(analysis: dict[str, Any]) -> None:
    metadata = analysis.get("metadata") or {}
    existing = db.all_policies()
    best: tuple[PolicyDocument, float, str] | None = None
    for policy in existing:
        score, reason = _policy_match_score(metadata, policy)
        if not best or score > best[1]:
            best = (policy, score, reason)
    if not best or best[1] < 0.45:
        analysis["version_match"] = {"decision": "new_policy", "confidence": best[1] if best else 0, "reason": "未发现相似制度"}
        return
    policy, confidence, reason = best
    decision = "auto_version" if confidence >= 0.86 else "needs_confirmation"
    question = f"疑似为《{policy.name}》（编号：{policy.code}）的新版本，是否作为该制度的新版本保存？"
    analysis["version_match"] = {
        "decision": decision,
        "policy_id": policy.id,
        "policy_name": policy.name,
        "policy_code": policy.code,
        "confidence": round(confidence, 3),
        "reason": reason,
        "question": question if decision == "needs_confirmation" else "",
    }
    if decision == "needs_confirmation":
        questions = list(analysis.get("questions") or [])
        if question not in questions:
            questions.insert(0, question)
        analysis["questions"] = questions


def _policy_match_score(metadata: dict[str, Any], policy: PolicyDocument) -> tuple[float, str]:
    code = _normalize(str(metadata.get("code") or ""))
    policy_code = _normalize(policy.code)
    if code and code != "待确认" and policy_code and code == policy_code:
        return 0.98, "制度编号完全一致"
    name = str(metadata.get("name") or "")
    category = str(metadata.get("category") or "")
    org_scope = str(metadata.get("org_scope") or "")
    name_score = SequenceMatcher(None, _normalize(name), _normalize(policy.name)).ratio() if name else 0
    theme_score = SequenceMatcher(
        None,
        _normalize(f"{name} {category} {org_scope}"),
        _normalize(f"{policy.name} {policy.category} {policy.org_scope}"),
    ).ratio()
    score = max(name_score * 0.75 + theme_score * 0.25, theme_score * 0.8)
    return score, f"名称相似度 {name_score:.2f}，制度主题相似度 {theme_score:.2f}"


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if not ch.isspace() and ch not in "《》（）()[]【】_-—")


def _resolve_version_target(version_match: dict[str, Any], answers: dict[str, str]) -> PolicyDocument | None:
    decision = version_match.get("decision")
    policy_id = str(version_match.get("policy_id") or "")
    if not policy_id or decision == "new_policy":
        return None
    matched = next((policy for policy in db.all_policies() if policy.id == policy_id), None)
    if not matched:
        return None
    if decision == "auto_version":
        return matched
    question = str(version_match.get("question") or "")
    answer = (answers.get(question) or "").strip()
    if not answer:
        raise ValueError("疑似匹配到已有制度，但置信度不足。请先确认是否作为已有制度的新版本保存。")
    if any(token in answer for token in ["否", "不是", "新制度", "单独", "新建"]):
        return None
    if any(token in answer for token in ["是", "确认", "同一", "新版本", "作为"]):
        return matched
    raise ValueError("请明确回复是否作为已有制度的新版本保存。")


def _field_value(field: str, answers: dict[str, str], metadata: dict[str, Any], fallback: str) -> str:
    return str(answers.get(field) or metadata.get(field) or fallback)


def source_file_for_analysis(analysis_id: str) -> tuple[Path, dict[str, Any]]:
    analysis = db.get_upload_session(analysis_id)
    if not analysis or not analysis.get("source_file"):
        raise ValueError("源文件不存在。")
    source = analysis["source_file"]
    return _source_file_path(source), source


def source_file_for_policy(policy: PolicyDocument) -> tuple[Path, dict[str, Any]]:
    if not policy.source_file:
        raise ValueError("源文件不存在。")
    source = policy.source_file.model_dump()
    return _source_file_path(source), source


def source_file_for_policy_version(policy_id: str, version_id: str) -> tuple[Path, dict[str, Any]]:
    version = db.fetch_policy_version(policy_id, version_id)
    if not version or not version.source_file:
        raise ValueError("源文件不存在。")
    source = version.source_file.model_dump()
    return _source_file_path(source), source


def _save_source_file(analysis_id: str, file_name: str, source_bytes: bytes, content_type: str) -> dict[str, Any]:
    suffix = Path(file_name).suffix.lower()
    stored_name = f"{analysis_id}{suffix or '.bin'}"
    path = _source_file_path({"stored_name": stored_name})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source_bytes)
    return {
        "file_name": file_name,
        "stored_name": stored_name,
        "content_type": content_type or "application/octet-stream",
        "size": len(source_bytes),
    }


def _source_file_path(source: dict[str, Any]) -> Path:
    root = Path(os.getenv("POLICY_SOURCE_DIR", "backend/uploads/policy_sources"))
    stored_name = Path(str(source["stored_name"])).name
    return root / stored_name


__all__ = [
    "analyze_policy_text",
    "extract_upload_text",
    "extract_upload_text_from_bytes",
    "save_policy_analysis",
    "source_file_for_analysis",
    "source_file_for_policy",
    "source_file_for_policy_version",
]
