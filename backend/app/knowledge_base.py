from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from app.hooks import hooks
from app.models import ClarificationQuestion, ProfessionalReference


@dataclass(frozen=True)
class KnowledgeBaseSettings:
    api_url: str
    api_key: str
    enabled: bool


def load_knowledge_base_settings() -> KnowledgeBaseSettings:
    return KnowledgeBaseSettings(
        api_url=os.getenv("KNOWLEDGE_API_URL", "http://127.0.0.1:8765"),
        api_key=os.getenv("KNOWLEDGE_API_KEY", ""),
        enabled=os.getenv("KNOWLEDGE_BASE_ENABLED", "true").lower() == "true",
    )


def _question_id(index: int, prefix: str = "kbq") -> str:
    return f"{prefix}_{index + 1}"


class KnowledgeBaseClient:
    def __init__(self, settings: KnowledgeBaseSettings | None = None) -> None:
        self.settings = settings or load_knowledge_base_settings()

    def _headers(self) -> dict[str, str]:
        if not self.settings.api_key:
            return {}
        return {"X-API-Key": self.settings.api_key}

    def ask(self, question: str, context: str = "", limit: int = 6) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"available": False, "reason": "disabled", "references": [], "knowledge_gaps": []}
        payload = {"question": question, "context": context, "output_mode": "answer", "limit": limit}
        try:
            with httpx.Client(timeout=5, trust_env=False) as client:
                response = client.post(
                    f"{self.settings.api_url.rstrip('/')}/v1/query",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            hooks.emit("knowledge_base_unavailable", {"question": question[:120], "reason": str(exc)})
            return {"available": False, "reason": str(exc), "references": [], "knowledge_gaps": []}
        hooks.emit(
            "knowledge_base_queried",
            {
                "question": question[:160],
                "confidence": data.get("confidence"),
                "reference_count": len(data.get("references", [])),
                "knowledge_gap_count": len(data.get("knowledge_gaps", [])),
            },
        )
        return {"available": True, **data}


def professional_references_from_kb(data: dict[str, Any], limit: int = 5) -> list[ProfessionalReference]:
    references: list[ProfessionalReference] = []
    context_by_id = {str(item.get("reference_id")): item for item in data.get("retrieved_context", []) if isinstance(item, dict)}
    context_by_path = {str(item.get("path")): item for item in data.get("retrieved_context", []) if isinstance(item, dict)}
    for item in data.get("references", [])[:limit]:
        if isinstance(item, str):
            references.append(ProfessionalReference(source=item, title=item))
            continue
        if not isinstance(item, dict):
            continue
        reference_id = str(item.get("reference_id") or item.get("id") or "")
        path = str(item.get("path") or item.get("source") or "")
        hit = context_by_id.get(reference_id) or context_by_path.get(path) or {}
        source = str(path or item.get("id") or item.get("title") or "knowledge_base")
        title = str(item.get("title") or item.get("name") or source)
        snippet = str(item.get("snippet") or hit.get("snippet") or item.get("quote") or item.get("summary") or "")
        hit_content = str(hit.get("content") or hit.get("snippet") or snippet)
        references.append(
            ProfessionalReference(
                source=source,
                title=title,
                snippet=snippet[:500],
                confidence=data.get("confidence"),
                reference_id=reference_id,
                source_kind=str(item.get("source_kind") or hit.get("source_kind") or ""),
                path=path,
                hit_content=hit_content[:1200],
                impact=_reference_impact(title, data),
            )
        )
    return references


def _reference_impact(title: str, data: dict[str, Any]) -> str:
    answer = str(data.get("answer") or "").strip()
    if not answer:
        return "用于提供制度解读、流程治理、合规风险和控制点判断的专业背景。"
    compact = " ".join(line.strip() for line in answer.splitlines() if line.strip())
    if len(compact) <= 420:
        return compact
    return compact[:420] + "..."


def clarification_questions_from_kb(data: dict[str, Any]) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    if not data.get("available"):
        questions.append(
            ClarificationQuestion(
                id="kb_unavailable",
                question="专业知识库当前不可用。是否允许本次仅基于制度和流程证据先生成待复核结论？",
                reason=str(data.get("reason") or "未能连接本地知识库服务。"),
                blocking=False,
                source="knowledge_base",
            )
        )
        return questions

    for index, gap in enumerate(data.get("knowledge_gaps", [])[:5]):
        text = gap if isinstance(gap, str) else str(gap.get("term") or gap.get("name") or gap)
        if not text:
            continue
        questions.append(
            ClarificationQuestion(
                id=_question_id(index),
                question=f"知识库对“{text}”覆盖不足。请确认它在本企业制度/流程中的定义或适用边界。",
                reason="知识库返回 knowledge_gaps，需要用户补充企业事实或术语定义。",
                blocking=False,
                source="knowledge_base",
            )
        )
    return questions


def build_skill_kb_question(skill_id: str, skill_name: str, policy_names: list[str], process_names: list[str]) -> str:
    names = "、".join(policy_names + process_names) or "当前选中的制度和流程"
    if skill_id == "skill_policy_conflict":
        return f"针对{names}，从制度解读、合规管控、审批权限和流程治理角度，执行多制度冲突检查时应重点关注哪些专业判断标准和不确定性？"
    if skill_id == "skill_policy_process_check":
        return f"针对{names}，从制度落地到BPMN流程、控制点、管理记录、合规审查和流程断点角度，制度与流程校验应关注哪些专业判断标准和不确定性？"
    if skill_id == "skill_no_policy_basis":
        return f"针对{names}，识别审批流无制度依据时，如何区分正式规则缺口、角色义务缺口、管理记录缺口和需要人工确认的事实？"
    if skill_id == "skill_upload_policy_file":
        return "制度文件入库审查时，如何判断制度框架是否合理、条款是否可解析、角色职责是否适合进入角色清单，以及哪些缺口需要用户确认？"
    return f"执行{skill_name}时需要哪些流程管理、制度解读和合规管控专业判断标准？"
