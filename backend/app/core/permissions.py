from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    ASSET_READ = "asset:read"
    ASSET_CREATE = "asset:create"
    ASSET_UPDATE = "asset:update"
    ASSET_SUBMIT_REVIEW = "asset:submit_review"
    ASSET_APPROVE = "asset:approve"
    ASSET_PUBLISH = "asset:publish"
    ASSET_ARCHIVE = "asset:archive"
    FINDING_READ = "finding:read"
    FINDING_UPDATE = "finding:update"
    SKILL_RUN = "skill:run"
    SKILL_AUDIT_READ = "skill:audit_read"
    RBAC_MANAGE = "rbac:manage"


class Role(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    INSTITUTION_ADMIN = "institution_admin"
    BUSINESS_OWNER = "business_owner"
    RISK_COMPLIANCE = "risk_compliance"
    AUDITOR = "auditor"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SYSTEM_ADMIN: frozenset(Permission),
    Role.INSTITUTION_ADMIN: frozenset(
        {
            Permission.ASSET_READ,
            Permission.ASSET_CREATE,
            Permission.ASSET_UPDATE,
            Permission.ASSET_SUBMIT_REVIEW,
            Permission.ASSET_PUBLISH,
            Permission.FINDING_READ,
            Permission.FINDING_UPDATE,
            Permission.SKILL_RUN,
            Permission.SKILL_AUDIT_READ,
        }
    ),
    Role.BUSINESS_OWNER: frozenset(
        {
            Permission.ASSET_READ,
            Permission.ASSET_UPDATE,
            Permission.ASSET_SUBMIT_REVIEW,
            Permission.FINDING_READ,
            Permission.SKILL_RUN,
        }
    ),
    Role.RISK_COMPLIANCE: frozenset(
        {
            Permission.ASSET_READ,
            Permission.ASSET_APPROVE,
            Permission.FINDING_READ,
            Permission.FINDING_UPDATE,
            Permission.SKILL_RUN,
            Permission.SKILL_AUDIT_READ,
        }
    ),
    Role.AUDITOR: frozenset({Permission.ASSET_READ, Permission.FINDING_READ, Permission.SKILL_AUDIT_READ}),
    Role.VIEWER: frozenset({Permission.ASSET_READ, Permission.FINDING_READ}),
}


def permissions_for_role(role: Role | str) -> frozenset[Permission]:
    normalized = role if isinstance(role, Role) else Role(role)
    return ROLE_PERMISSIONS[normalized]


def has_permission(role: Role | str, permission: Permission | str) -> bool:
    normalized_permission = permission if isinstance(permission, Permission) else Permission(permission)
    return normalized_permission in permissions_for_role(role)


def permission_matrix() -> dict[str, list[str]]:
    return {
        role.value: sorted(permission.value for permission in permissions)
        for role, permissions in ROLE_PERMISSIONS.items()
    }
