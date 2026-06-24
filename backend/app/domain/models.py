from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.status import AssetStatus, FindingStatus, JobStatus, UploadStatus, VersionStatus


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantScopedMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Policy(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_policies_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    org_scope: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), default=AssetStatus.DRAFT.value, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    versions: Mapped[list[PolicyVersion]] = relationship(back_populates="policy", cascade="all, delete-orphan")


class PolicyVersion(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version_no", name="uq_policy_versions_policy_version_no"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=VersionStatus.DRAFT.value, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    policy: Mapped[Policy] = relationship(back_populates="versions")
    clauses: Mapped[list[PolicyClause]] = relationship(back_populates="version", cascade="all, delete-orphan")


class PolicyClause(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "policy_clauses"
    __table_args__ = (UniqueConstraint("version_id", "clause_no", name="uq_policy_clauses_version_clause_no"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("policy_clauses.id"), nullable=True)
    clause_no: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    version: Mapped[PolicyVersion] = relationship(back_populates="clauses")


class ProcessDefinition(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "process_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_process_definitions_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    business_domain: Mapped[str] = mapped_column(String(128), nullable=False)
    org_scope: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), default=AssetStatus.DRAFT.value, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    versions: Mapped[list[ProcessVersion]] = relationship(back_populates="process", cascade="all, delete-orphan")


class ProcessVersion(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "process_versions"
    __table_args__ = (UniqueConstraint("process_id", "version_no", name="uq_process_versions_process_version_no"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=VersionStatus.DRAFT.value, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    bpmn_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    process: Mapped[ProcessDefinition] = relationship(back_populates="versions")
    nodes: Mapped[list[ProcessNode]] = relationship(back_populates="version", cascade="all, delete-orphan")


class ProcessNode(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "process_nodes"
    __table_args__ = (UniqueConstraint("version_id", "bpmn_element_id", name="uq_process_nodes_version_bpmn_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("process_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    bpmn_element_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version: Mapped[ProcessVersion] = relationship(back_populates="nodes")


class KnowledgeNode(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (UniqueConstraint("tenant_id", "node_type", "name", name="uq_knowledge_nodes_tenant_type_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_type: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class KnowledgeEdge(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class Finding(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=FindingStatus.PENDING_REVIEW.value, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assumption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    evidence: Mapped[list[Evidence]] = relationship(back_populates="finding", cascade="all, delete-orphan")


class Evidence(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence")


class RoleMapping(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "role_mappings"
    __table_args__ = (UniqueConstraint("tenant_id", "policy_role", "process_role", name="uq_role_mappings_roles"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_role: Mapped[str] = mapped_column(String(256), nullable=False)
    process_role: Mapped[str] = mapped_column(String(256), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="mapped", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)


class UploadSession(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), default=UploadStatus.RECEIVED.value, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/octet-stream")
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    analysis_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)


class SkillRun(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "skill_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED.value, nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)


class OutboxEvent(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED.value, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
