from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

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
from app.skill_registry import get_skill_spec

KG_TYPE_ALIASES = {
    "Role": "人员角色",
    "角色": "人员角色",
    "人员角色": "人员角色",
    "岗位": "人员角色",
    "Position": "人员角色",
    "Department": "部门组织",
    "部门": "部门组织",
    "组织": "部门组织",
    "组织部门": "部门组织",
    "部门组织": "部门组织",
    "Organization": "部门组织",
    "OrgUnit": "部门组织",
    "BusinessRule": "业务规则",
    "Rule": "业务规则",
    "业务规则": "业务规则",
    "规则": "业务规则",
    "Condition": "业务规则",
}


def _safe_id(prefix: str, text: str | None = None) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]+", "_", text or "")[:32].strip("_").lower()
    random_part = uuid4().hex[:8]
    return f"{prefix}_{suffix}_{random_part}" if suffix else f"{prefix}_{random_part}"


async def extract_upload_text(file: UploadFile) -> str:
    data = await file.read()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".pdf":
        temp_path = Path("backend") / f"upload_{uuid4().hex}.pdf"
        temp_path.write_bytes(data)
        try:
            reader = PdfReader(str(temp_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        finally:
            temp_path.unlink(missing_ok=True)
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="ignore")
    raise ValueError("当前仅支持 PDF、TXT、Markdown 文件。")


def _split_clauses(text: str, policy_id: str) -> list[dict[str, Any]]:
    lines = _policy_body_lines(text)
    clauses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    index_by_clause_no: dict[str, str] = {}
    current_numeric_no = ""
    pattern = re.compile(r"^(?P<num>\d+(?:\.\d+){0,5})(?:\s+|[、.．])(?P<title>.+)?$")
    bullet_pattern = re.compile(r"^[（(](?P<num>\d+|[一二三四五六七八九十]+)[）)]\s*(?P<title>.+)$")

    def append_current() -> None:
        if current and current["content"].strip():
            clauses.append(current)

    def parent_for_clause(clause_no: str) -> str | None:
        if "(" in clause_no:
            return index_by_clause_no.get(current_numeric_no)
        parts = clause_no.split(".")
        if len(parts) <= 1:
            return None
        return index_by_clause_no.get(".".join(parts[:-1]))

    def start_clause(clause_no: str, title: str, line: str) -> None:
        nonlocal current, current_numeric_no
        append_current()
        if "(" not in clause_no:
            current_numeric_no = clause_no
        clause_id = f"clause_{policy_id}_{len(clauses) + 1}"
        current = {
            "id": clause_id,
            "policy_id": policy_id,
            "clause_no": clause_no,
            "title": title[:80] or f"条款 {clause_no}",
            "content": line,
            "parent_id": parent_for_clause(clause_no),
            "order_index": len(clauses) + 1,
        }
        index_by_clause_no[clause_no] = clause_id

    for line in lines:
        match = pattern.match(line)
        if match:
            clause_no = match.group("num")
            title = (match.group("title") or "").strip()
            start_clause(clause_no, title, line)
            continue
        bullet_match = bullet_pattern.match(line)
        if bullet_match and current_numeric_no:
            bullet_no = bullet_match.group("num")
            clause_no = f"{current_numeric_no}({bullet_no})"
            title = bullet_match.group("title").strip()
            start_clause(clause_no, title, line)
        elif current:
            current["content"] = f"{current['content']}\n{line}"
    if current:
        clauses.append(current)
    return clauses[:160]


def _policy_body_lines(text: str) -> list[str]:
    lines: list[str] = []
    skip_patterns = [
        re.compile(r"^文件名\s+"),
        re.compile(r"^编号\s+.+页码\s+"),
        re.compile(r"^编制\s+.+生效日期\s+.+页码\s+"),
        re.compile(r"^第\s*\d+\s*页[，,]\s*共\s*\d+\s*页$"),
    ]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in skip_patterns):
            continue
        lines.append(line)
    return lines


def _extract_metadata(text: str) -> dict[str, str]:
    first_lines = "\n".join(text.splitlines()[:20])
    name_match = re.search(r"(?:文件名\s*)?([^\n]{4,80}(?:制度|办法|细则|指引|规范))", first_lines)
    code_match = re.search(r"(?:编号|制度编号)\s*([A-Z0-9.\-]+)", first_lines)
    version_match = re.search(r"(?:版本|版号)\s*([A-Za-z0-9/.\-]+)", first_lines)
    date_match = re.search(r"(?:生效日期|发布日期)\s*([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})", first_lines)
    module_match = re.search(r"(?:所属模块|模块|类别)\s*([^\s\n]+)", first_lines)
    return {
        "name": name_match.group(1).strip() if name_match else "未命名制度",
        "code": code_match.group(1).strip() if code_match else "",
        "version": version_match.group(1).strip() if version_match else "",
        "effective_date": date_match.group(1).replace("/", "-") if date_match else "",
        "category": module_match.group(1).strip() if module_match else "",
        "org_scope": "待确认",
    }


def _extract_concepts(text: str) -> list[dict[str, str]]:
    candidates = {
        "人员角色": ["采购中心", "采购管理部门", "采购实施部门", "决策小组", "风控", "人力资源负责人", "分管领导", "平台公司业务分管领导", "部门负责人", "平台总经理", "子公司总经理"],
        "部门组织": ["生产管理中心", "生产管理部", "饲料产品部", "饲料厂", "财务运营部", "数字化部", "下属企业"],
    }
    concepts = []
    for node_type, terms in candidates.items():
        for term in terms:
            if term in text:
                concepts.append({"node_type": node_type, "name": term})
    for match in re.finditer(r"(?:金额|单笔金额|采购金额)?超过\s*\d+\s*万元[^。；\n]{0,40}(?:审批|复核|备案|决策)", text):
        concepts.append({"node_type": "业务规则", "name": match.group(0).strip("，；。 ")})
    for match in re.finditer(r"[^。；\n]{0,30}(?:需|应|必须|不得)[^。；\n]{0,50}(?:审批|复核|备案|决策|记录|归档)", text):
        rule = match.group(0).strip("，；。 ")
        if 6 <= len(rule) <= 80:
            concepts.append({"node_type": "业务规则", "name": rule})
    return _filter_concepts(concepts)


def _filter_concepts(concepts: list[dict[str, Any]]) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for concept in concepts:
        node_type = KG_TYPE_ALIASES.get(str(concept.get("node_type", "")).strip())
        name = str(concept.get("name", "")).strip()
        if not node_type or not name:
            continue
        if len(name) > 100:
            continue
        key = (node_type, name)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"node_type": node_type, "name": name})
    return filtered


def _policy_like_signals(text: str, metadata: dict[str, str], clauses: list[dict[str, Any]]) -> dict[str, bool]:
    first_page = text[:3000]
    policy_keywords = ["制度", "办法", "细则", "指引", "规范", "规程", "规定", "管理要求"]
    governance_keywords = ["目的", "适用范围", "职责", "流程", "审批", "监督", "附则", "管理", "要求"]
    return {
        "has_enough_text": len(text.strip()) >= 120,
        "has_policy_name": metadata.get("name") != "未命名制度" or any(keyword in first_page for keyword in policy_keywords),
        "has_policy_keyword": any(keyword in first_page for keyword in policy_keywords),
        "has_governance_content": sum(1 for keyword in governance_keywords if keyword in text) >= 2,
        "has_clause_structure": len(clauses) >= 2,
    }


def _hard_rejection_reasons(text: str, metadata: dict[str, str], clauses: list[dict[str, Any]]) -> list[str]:
    signals = _policy_like_signals(text, metadata, clauses)
    reasons: list[str] = []
    if not signals["has_enough_text"]:
        reasons.append("文档文本过短，无法形成可解析的制度正文。")
    if not signals["has_policy_name"] and not signals["has_policy_keyword"]:
        reasons.append("未识别到制度、办法、细则、指引、规范等制度型文件特征。")
    if not signals["has_clause_structure"] and not signals["has_governance_content"]:
        reasons.append("未识别到章节条款结构或职责、流程、审批、管理要求等治理内容。")
    return reasons


def _normalize_admission(
    analysis: dict[str, Any],
    text: str,
    metadata: dict[str, str],
    clauses: list[dict[str, Any]],
) -> dict[str, Any]:
    hard_reasons = _hard_rejection_reasons(text, metadata, clauses)
    original_suitable = bool(analysis.get("suitable"))
    model_reasons = [str(reason).strip() for reason in analysis.get("reasons", []) if str(reason).strip()]
    existing_questions = [str(question).strip() for question in analysis.get("questions", []) if str(question).strip()]
    suggestions = [str(item).strip() for item in analysis.get("suggestions", []) if str(item).strip()]

    if hard_reasons:
        analysis["suitable"] = False
        analysis["rejection_level"] = "hard"
        analysis["can_force_upload"] = False
        analysis["reasons"] = hard_reasons
        analysis["questions"] = existing_questions
        analysis["suggestions"] = suggestions + [issue for issue in model_reasons if issue not in suggestions]
        return analysis

    soft_issues = model_reasons if not original_suitable else []
    analysis["suitable"] = True
    analysis["rejection_level"] = "none"
    analysis["can_force_upload"] = True
    analysis["reasons"] = []
    analysis["questions"] = _filter_upload_questions(existing_questions)
    analysis["suggestions"] = suggestions + [issue for issue in soft_issues if issue not in suggestions]
    return analysis


def _filter_upload_questions(questions: list[str]) -> list[str]:
    allowed_keywords = ["制度名称", "编号", "版本", "生效日期", "保存", "结构项", "分类", "同一主体", "同一角色", "同一组织", "引用文件", "入库范围"]
    blocked_keywords = ["角色未定义", "术语未定义", "监督检查", "违规追责", "后续再补充完善", "不影响本次先入库"]
    filtered: list[str] = []
    for question in questions:
        if any(keyword in question for keyword in blocked_keywords):
            continue
        if any(keyword in question for keyword in allowed_keywords):
            filtered.append(question)
    return filtered


def _heuristic_analysis(text: str, file_name: str) -> dict[str, Any]:
    metadata = _extract_metadata(text)
    temp_policy_id = _safe_id("policy", metadata["name"])
    clauses = _split_clauses(text, temp_policy_id)
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
        "concepts": _extract_concepts(text),
        "professional_references": [],
        "professional_questions": [],
        "text_preview": text[:1200],
    }
    return _normalize_admission(analysis, text, metadata, clauses)


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
    system_prompt = (
        f"{spec.prompt}\n\n"
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
    user_prompt = json.dumps(
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
    hooks.emit("before_llm_call", {"skill_id": "skill_upload_policy_file", "model": load_deepseek_settings().model})
    try:
        result = DeepSeekClient().chat_json(system_prompt, user_prompt)
        hooks.emit("after_llm_call", {"skill_id": "skill_upload_policy_file", "finding_count": 0})
    except Exception as exc:
        hooks.emit("upload_analysis_fallback", {"reason": str(exc)})
        analysis = _heuristic_analysis(text, file_name)
        analysis["professional_references"] = professional_references
        analysis["professional_questions"] = professional_questions
        return analysis
    fallback = _heuristic_analysis(text, file_name)
    metadata = {**fallback["metadata"], **result.get("metadata", {})}
    policy_id = _safe_id("policy", metadata.get("name") or file_name)
    raw_clauses = fallback["clauses"]
    clauses = []
    scoped_raw_clauses = raw_clauses[:160]
    id_map = {item.get("id"): f"clause_{policy_id}_{idx + 1}" for idx, item in enumerate(scoped_raw_clauses)}
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
    analysis = {
        "analysis_id": "",
        "file_name": file_name,
        "suitable": bool(result.get("suitable", fallback["suitable"])),
        "reasons": result.get("reasons", fallback["reasons"]),
        "suggestions": result.get("suggestions", fallback["suggestions"]),
        "questions": result.get("questions", fallback["questions"]),
        "metadata": metadata,
        "clauses": clauses,
        "concepts": _filter_concepts(result.get("concepts", fallback["concepts"])),
        "professional_references": professional_references,
        "professional_questions": professional_questions,
        "text_preview": text[:1200],
    }
    return _normalize_admission(analysis, text, metadata, clauses)


def analyze_policy_text(text: str, file_name: str) -> dict[str, Any]:
    analysis = _llm_analysis(text, file_name)
    analysis_id = _safe_id("upload", file_name)
    analysis["analysis_id"] = analysis_id
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
    policy_id = _safe_id("policy", metadata.get("name") or analysis["file_name"])
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
    policy = PolicyDocument(
        id=policy_id,
        name=answers.get("name") or metadata.get("name") or analysis["file_name"],
        code=answers.get("code") or metadata.get("code") or "待确认",
        version=answers.get("version") or metadata.get("version") or "待确认",
        category=category or metadata.get("category") or "未分类",
        org_scope=answers.get("org_scope") or metadata.get("org_scope") or "待确认",
        status="effective",
        effective_date=answers.get("effective_date") or metadata.get("effective_date") or "待确认",
        clauses=clauses,
    )
    db.insert_policy(policy)
    hooks.emit(
        "policy_upload_saved",
        {
            "analysis_id": analysis_id,
            "policy_id": policy.id,
            "category": policy.category,
            "clause_count": len(policy.clauses),
            "role_candidate_count": len(analysis.get("concepts", [])),
            "clarification_answer_count": len(answers),
            "clarification_answers": answers,
        },
    )
    return policy
