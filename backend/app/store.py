from __future__ import annotations

from app import db
from app.models import Finding, KnowledgeEdge, KnowledgeNode, PolicyDocument, ProcessDefinition, SkillDefinition
from app.role_inventory import role_count
from app.skill_registry import get_skill_spec, list_skill_definitions


class DemoStore:
    def __init__(self) -> None:
        db.ensure_database()

    def reset(self) -> None:
        db.reset_database()

    def dashboard_summary(self) -> dict:
        findings = db.fetch_findings()
        return {
            "policy_count": len(db.fetch_all("policies")),
            "process_count": len(db.fetch_all("processes")),
            "knowledge_node_count": role_count(),
            "finding_count": len(findings),
            "pending_review_count": sum(1 for item in findings if item.status == "pending_review"),
            "closed_count": sum(1 for item in findings if item.status == "closed"),
        }

    def all(self, key: str):
        table_map = {
            "policies": ("policies", PolicyDocument),
            "processes": ("processes", ProcessDefinition),
            "knowledge_nodes": ("knowledge_nodes", KnowledgeNode),
            "knowledge_edges": ("knowledge_edges", KnowledgeEdge),
            "findings": ("findings", Finding),
        }
        if key == "skills":
            return list_skill_definitions()
        table, model = table_map[key]
        return [model.model_validate(item) for item in db.fetch_all(table)]

    def get_policy(self, policy_id: str):
        item = db.fetch_one("policies", policy_id)
        return PolicyDocument.model_validate(item) if item else None

    def get_process(self, process_id: str):
        item = db.fetch_one("processes", process_id)
        return ProcessDefinition.model_validate(item) if item else None

    def delete_policy(self, policy_id: str) -> bool:
        return db.delete_policy(policy_id)

    def delete_process(self, process_id: str) -> bool:
        return db.delete_process(process_id)

    def get_skill(self, skill_id: str):
        spec = get_skill_spec(skill_id)
        return spec.definition if spec else None

    def insert_finding(self, finding: Finding) -> None:
        db.insert_finding(finding)

    def update_finding_status(self, finding_id: str, status: str):
        return db.update_finding_status(finding_id, status)


store = DemoStore()
