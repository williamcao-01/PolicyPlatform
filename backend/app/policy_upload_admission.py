from __future__ import annotations

from typing import Any


def normalize_upload_admission(
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

