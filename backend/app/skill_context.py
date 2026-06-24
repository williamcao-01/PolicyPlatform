from __future__ import annotations

import json

from app import db
from app.knowledge_base import (
    KnowledgeBaseClient,
    build_skill_kb_question,
    clarification_questions_from_kb,
    professional_references_from_kb,
)
from app.models import ClarificationQuestion, ProfessionalReference, SkillRunRequest


def build_skill_context(request: SkillRunRequest) -> dict:
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


def load_professional_context(
    request: SkillRunRequest,
    context: dict,
    spec_name: str,
) -> tuple[dict, list[ProfessionalReference], list[ClarificationQuestion]]:
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

