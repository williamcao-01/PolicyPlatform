from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class TransitionSpec:
    name: str
    states: frozenset[str]
    initial: str
    terminal: frozenset[str]
    transitions: frozenset[tuple[str, str]]


@dataclass(frozen=True)
class PermissionRule:
    role: str
    permissions: frozenset[str]


RBAC_ROLES: Final[frozenset[str]] = frozenset(
    {
        "system_admin",
        "institution_admin",
        "business_owner",
        "risk_compliance",
        "auditor",
        "viewer",
    }
)

RBAC_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        "asset:read",
        "asset:create",
        "asset:update",
        "asset:submit_review",
        "asset:approve",
        "asset:publish",
        "asset:archive",
        "finding:read",
        "finding:update",
        "skill:run",
        "skill:audit_read",
        "rbac:manage",
    }
)

RBAC_MATRIX: Final[tuple[PermissionRule, ...]] = (
    PermissionRule("system_admin", RBAC_PERMISSIONS),
    PermissionRule(
        "institution_admin",
        frozenset(
            {
                "asset:read",
                "asset:create",
                "asset:update",
                "asset:submit_review",
                "asset:publish",
                "finding:read",
                "finding:update",
                "skill:run",
                "skill:audit_read",
            }
        ),
    ),
    PermissionRule(
        "business_owner",
        frozenset({"asset:read", "asset:update", "asset:submit_review", "finding:read", "skill:run"}),
    ),
    PermissionRule(
        "risk_compliance",
        frozenset({"asset:read", "asset:approve", "finding:read", "finding:update", "skill:run", "skill:audit_read"}),
    ),
    PermissionRule("auditor", frozenset({"asset:read", "finding:read", "skill:audit_read"})),
    PermissionRule("viewer", frozenset({"asset:read", "finding:read"})),
)

ASSET_STATE_MACHINE: Final[TransitionSpec] = TransitionSpec(
    name="asset_lifecycle",
    states=frozenset({"draft", "in_review", "approved", "published", "archived", "rejected"}),
    initial="draft",
    terminal=frozenset({"archived"}),
    transitions=frozenset(
        {
            ("draft", "in_review"),
            ("in_review", "approved"),
            ("in_review", "rejected"),
            ("rejected", "draft"),
            ("approved", "published"),
            ("published", "archived"),
        }
    ),
)

ASYNC_TASK_STATE_MACHINE: Final[TransitionSpec] = TransitionSpec(
    name="async_task_lifecycle",
    states=frozenset({"queued", "running", "succeeded", "failed", "cancelled"}),
    initial="queued",
    terminal=frozenset({"succeeded", "failed", "cancelled"}),
    transitions=frozenset(
        {
            ("queued", "running"),
            ("queued", "cancelled"),
            ("running", "succeeded"),
            ("running", "failed"),
            ("running", "cancelled"),
        }
    ),
)

AI_AUDIT_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "before_llm_call",
        "after_llm_call",
        "skill_run_failed",
        "finding_verification_failed",
        "upload_analysis_fallback",
    }
)

AI_AUDIT_REQUIRED_PAYLOAD_KEYS: Final[dict[str, frozenset[str]]] = {
    "before_llm_call": frozenset({"skill_id", "model"}),
    "after_llm_call": frozenset({"skill_id", "finding_count"}),
    "skill_run_failed": frozenset({"skill_id", "reason"}),
    "finding_verification_failed": frozenset({"skill_id", "reason"}),
    "upload_analysis_fallback": frozenset({"reason"}),
}

MAIN_CHAIN_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/policy-uploads/analyze"),
        ("POST", "/api/policy-uploads/{analysis_id}/save"),
        ("GET", "/api/policies/{policy_id}"),
        ("GET", "/api/policies/{policy_id}/versions"),
        ("GET", "/api/policies/{policy_id}/source"),
        ("POST", "/api/skill-runs"),
        ("GET", "/api/findings"),
        ("PATCH", "/api/findings/{finding_id}"),
        ("GET", "/api/exports/findings.xlsx"),
        ("GET", "/api/hooks/events"),
    }
)

PROTECTED_ROUTE_CONTRACT: Final[dict[tuple[str, str], str]] = {
    ("POST", "/api/policy-uploads/analyze"): "asset:create",
    ("POST", "/api/policy-uploads/{analysis_id}/save"): "asset:create",
    ("DELETE", "/api/policies/{policy_id}"): "asset:archive",
    ("DELETE", "/api/processes/{process_id}"): "asset:archive",
    ("POST", "/api/skill-runs"): "skill:run",
    ("PATCH", "/api/findings/{finding_id}"): "finding:update",
    ("GET", "/api/hooks/events"): "skill:audit_read",
}

PLANNED_ASYNC_TASK_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/tasks"),
        ("GET", "/api/tasks/{task_id}"),
        ("POST", "/api/tasks/{task_id}/cancel"),
    }
)

PLANNED_ASSET_LIFECYCLE_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/assets/{asset_id}/submit-review"),
        ("POST", "/api/assets/{asset_id}/approve"),
        ("POST", "/api/assets/{asset_id}/publish"),
        ("POST", "/api/assets/{asset_id}/archive"),
    }
)
