from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
FindingStatus = Literal["pending_review", "in_progress", "closed", "rejected"]
VerificationStatus = Literal["verified", "uncertain"]
VersionStatus = Literal["current", "historical"]


class PolicyClause(BaseModel):
    id: str
    policy_id: str
    clause_no: str
    title: str
    content: str
    parent_id: str | None = None
    order_index: int


class PolicySourceFile(BaseModel):
    file_name: str
    stored_name: str
    content_type: str = "application/octet-stream"
    size: int = 0


class PolicyDocument(BaseModel):
    id: str
    name: str
    code: str
    version: str
    category: str
    org_scope: str
    status: str
    effective_date: str
    clauses: list[PolicyClause] = Field(default_factory=list)
    source_file: PolicySourceFile | None = None
    current_version_id: str = ""
    version_count: int = 1


class PolicyVersion(BaseModel):
    id: str
    policy_id: str
    version_no: str
    effective_date: str
    status: VersionStatus = "current"
    created_at: str
    created_by: str = "system"
    change_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    clauses: list[PolicyClause] = Field(default_factory=list)
    source_file: PolicySourceFile | None = None


class ProcessNode(BaseModel):
    id: str
    process_id: str
    bpmn_element_id: str
    name: str
    role: str
    action: str
    condition: str | None = None
    order_index: int


class ProcessAsset(BaseModel):
    id: str
    process_id: str
    file_name: str
    bpmn_xml: str


class ProcessDefinition(BaseModel):
    id: str
    name: str
    code: str
    business_domain: str
    org_scope: str
    status: str
    nodes: list[ProcessNode] = Field(default_factory=list)
    asset: ProcessAsset
    current_version_id: str = ""
    version_count: int = 1


class ProcessVersion(BaseModel):
    id: str
    process_id: str
    version_no: str
    effective_date: str
    status: VersionStatus = "current"
    created_at: str
    created_by: str = "system"
    change_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    nodes: list[ProcessNode] = Field(default_factory=list)
    asset: ProcessAsset


class KnowledgeNode(BaseModel):
    id: str
    node_type: str
    name: str
    source_count: int = 1


class KnowledgeEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    confidence: float = 1.0


class RoleMention(BaseModel):
    asset_id: str
    asset_name: str
    item_id: str
    item_label: str
    quote: str


class RoleEntry(BaseModel):
    id: str
    name: str
    source: Literal["policy", "process"]
    mention_count: int
    mentions: list[RoleMention] = Field(default_factory=list)


class RoleMapping(BaseModel):
    id: str
    policy_role: str
    process_role: str
    confidence: float = 0.0
    mapping_type: Literal["auto", "manual"] = "auto"
    status: Literal["mapped", "unmapped", "ignored"] = "mapped"
    rationale: str = ""


class RoleInventory(BaseModel):
    policy_roles: list[RoleEntry]
    process_roles: list[RoleEntry]
    mappings: list[RoleMapping]


class Evidence(BaseModel):
    id: str
    source_type: Literal["policy_clause", "bpmn_node", "knowledge_node"]
    source_id: str
    label: str
    quote: str


class ProfessionalReference(BaseModel):
    source: str
    title: str = ""
    snippet: str = ""
    confidence: str | None = None
    reference_id: str = ""
    source_kind: str = ""
    path: str = ""
    hit_content: str = ""
    impact: str = ""


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    reason: str = ""
    blocking: bool = False
    source: str = "skill"


class Finding(BaseModel):
    id: str
    finding_type: str
    title: str
    description: str
    severity: Severity
    status: FindingStatus = "pending_review"
    closed_at: str | None = None
    confidence: float
    skill_id: str
    target_ids: list[str]
    evidence: list[Evidence]
    assumption: str = ""
    suggestion: str
    professional_references: list[ProfessionalReference] = Field(default_factory=list)
    verification_status: VerificationStatus = "verified"
    verification_note: str = ""
    policy_version_ids: list[str] = Field(default_factory=list)
    process_version_ids: list[str] = Field(default_factory=list)
    based_on_historical_version: bool = False


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    required_inputs: list[dict[str, Any]]
    output_types: list[str]
    can_update_assets: bool = False


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    message_type: str
    content: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SkillRunRequest(BaseModel):
    skill_id: str
    policy_ids: list[str] = Field(default_factory=list)
    process_ids: list[str] = Field(default_factory=list)
    knowledge_node_ids: list[str] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class SkillRunResult(BaseModel):
    id: str
    skill_id: str
    status: Literal["completed", "failed"]
    summary: str
    execution_steps: list[str] = Field(default_factory=list)
    final_answer: str = ""
    findings: list[Finding]
    hook_event_ids: list[str]
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    professional_references: list[ProfessionalReference] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    policy_count: int
    process_count: int
    knowledge_node_count: int
    finding_count: int
    pending_review_count: int
    closed_count: int
