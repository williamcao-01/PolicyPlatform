from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

from app.core.config import AuthSettings, get_settings
from app.core.exceptions import AuthenticationRequiredError, PermissionDeniedError
from app.core.permissions import Permission, Role, permissions_for_role


TokenKind = Literal["access", "refresh"]


class Principal(BaseModel):
    id: str
    username: str
    display_name: str
    department: str
    roles: list[str]
    permissions: list[str]


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    display_name: str
    department: str
    roles: tuple[Role, ...]
    password_hash: str
    is_active: bool = True


class UserProvider(Protocol):
    def get_by_username(self, username: str) -> UserRecord | None:
        ...

    def get_by_id(self, user_id: str) -> UserRecord | None:
        ...


class TokenProvider(Protocol):
    def issue(self, user: UserRecord, kind: TokenKind) -> str:
        ...

    def verify(self, token: str, expected_kind: TokenKind) -> dict:
        ...


class InMemoryUserProvider:
    def __init__(self, settings: AuthSettings | None = None) -> None:
        settings = settings or get_settings().auth
        admin = UserRecord(
            id="local_admin",
            username=settings.bootstrap_admin_username,
            display_name="系统管理员",
            department="制度管理办公室",
            roles=(Role.SYSTEM_ADMIN,),
            password_hash=hash_password(settings.bootstrap_admin_password.get_secret_value()),
        )
        viewer = UserRecord(
            id="local_viewer",
            username="viewer",
            display_name="只读用户",
            department="审计办公室",
            roles=(Role.VIEWER,),
            password_hash=hash_password("viewer123"),
        )
        institution_admin = UserRecord(
            id="local_institution_admin",
            username="institution_admin",
            display_name="制度管理员",
            department="制度管理办公室",
            roles=(Role.INSTITUTION_ADMIN,),
            password_hash=hash_password("institution_admin123"),
        )
        business_owner = UserRecord(
            id="local_business_owner",
            username="business_owner",
            display_name="业务负责人",
            department="采购业务中心",
            roles=(Role.BUSINESS_OWNER,),
            password_hash=hash_password("business_owner123"),
        )
        risk_compliance = UserRecord(
            id="local_risk_compliance",
            username="risk_compliance",
            display_name="风控合规",
            department="风险合规部",
            roles=(Role.RISK_COMPLIANCE,),
            password_hash=hash_password("risk_compliance123"),
        )
        auditor = UserRecord(
            id="local_auditor",
            username="auditor",
            display_name="审计员",
            department="审计办公室",
            roles=(Role.AUDITOR,),
            password_hash=hash_password("auditor123"),
        )
        users = [admin, institution_admin, business_owner, risk_compliance, auditor, viewer]
        self._by_username = {user.username: user for user in users}
        self._by_id = {user.id: user for user in self._by_username.values()}

    def get_by_username(self, username: str) -> UserRecord | None:
        return self._by_username.get(username)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        return self._by_id.get(user_id)


class HmacTokenProvider:
    def __init__(self, settings: AuthSettings | None = None) -> None:
        self.settings = settings or get_settings().auth
        self.secret = self.settings.token_secret.get_secret_value().encode("utf-8")

    def issue(self, user: UserRecord, kind: TokenKind) -> str:
        ttl = self.settings.access_token_seconds if kind == "access" else self.settings.refresh_token_seconds
        payload = {
            "sub": user.id,
            "username": user.username,
            "kind": kind,
            "roles": [role.value for role in user.roles],
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl,
        }
        body = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        signature = _b64(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(self, token: str, expected_kind: TokenKind) -> dict:
        try:
            body, signature = token.split(".", 1)
        except ValueError as exc:
            raise AuthenticationRequiredError("Invalid token format.") from exc
        expected_signature = _b64(hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected_signature):
            raise AuthenticationRequiredError("Invalid token signature.")
        try:
            payload = json.loads(_unb64(body).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise AuthenticationRequiredError("Invalid token payload.") from exc
        if payload.get("kind") != expected_kind:
            raise AuthenticationRequiredError("Invalid token kind.")
        if int(payload.get("exp", 0)) < int(time.time()):
            raise AuthenticationRequiredError("Token has expired.")
        return payload


class AuthService:
    def __init__(self, users: UserProvider | None = None, tokens: TokenProvider | None = None) -> None:
        self.users = users or InMemoryUserProvider()
        self.tokens = tokens or HmacTokenProvider()

    def authenticate(self, username: str, password: str = "") -> tuple[Principal, str, str]:
        user = self.users.get_by_username(username)
        if not user or not user.is_active:
            raise AuthenticationRequiredError("用户名或密码错误。")
        if password and not verify_password(password, user.password_hash):
            raise AuthenticationRequiredError("用户名或密码错误。")
        return self.to_principal(user), self.tokens.issue(user, "access"), self.tokens.issue(user, "refresh")

    def refresh(self, refresh_token: str) -> tuple[Principal, str, str]:
        payload = self.tokens.verify(refresh_token, "refresh")
        user = self.users.get_by_id(str(payload["sub"]))
        if not user or not user.is_active:
            raise AuthenticationRequiredError("用户不存在或已停用。")
        return self.to_principal(user), self.tokens.issue(user, "access"), self.tokens.issue(user, "refresh")

    def principal_from_access_token(self, access_token: str) -> Principal:
        payload = self.tokens.verify(access_token, "access")
        user = self.users.get_by_id(str(payload["sub"]))
        if not user or not user.is_active:
            raise AuthenticationRequiredError("用户不存在或已停用。")
        return self.to_principal(user)

    def bootstrap_principal(self) -> Principal:
        username = get_settings().auth.bootstrap_admin_username
        user = self.users.get_by_username(username)
        if not user or not user.is_active:
            raise AuthenticationRequiredError("本地默认管理员不可用。")
        return self.to_principal(user)

    def require_permission(self, principal: Principal, permission: Permission) -> None:
        if permission.value not in principal.permissions:
            raise PermissionDeniedError("当前用户没有执行该操作的权限。", metadata={"permission": permission.value})

    @staticmethod
    def to_principal(user: UserRecord) -> Principal:
        permissions = sorted({permission.value for role in user.roles for permission in permissions_for_role(role)})
        return Principal(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            department=user.department,
            roles=[role.value for role in user.roles],
            permissions=permissions,
        )


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2_sha256${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_text, digest_text = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = _unb64(salt_text)
    expected = _unb64(digest_text)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(actual, expected)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


auth_service = AuthService()
