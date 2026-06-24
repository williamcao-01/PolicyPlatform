from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.data.demo_seed import build_demo_dataset
from app.models import (
    Evidence,
    Finding,
    KnowledgeNode,
    PolicyDocument,
    PolicyVersion,
    ProcessDefinition,
    ProcessVersion,
    RoleMapping,
)


def db_path() -> Path:
    raw = os.getenv("DEMO_DB_PATH", "backend/demo.db")
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS policy_versions (
            id TEXT PRIMARY KEY,
            policy_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS processes (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS process_versions (
            id TEXT PRIMARY KEY,
            process_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS knowledge_edges (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS upload_sessions (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS role_mappings (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()


def _dump(model: Any) -> str:
    if hasattr(model, "model_dump"):
        return json.dumps(model.model_dump(), ensure_ascii=False)
    return json.dumps(model, ensure_ascii=False)


def _load(row: sqlite3.Row) -> dict:
    return json.loads(row["payload"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_version_id(prefix: str, asset_id: str, version_no: str) -> str:
    clean_asset = re.sub(r"[^0-9A-Za-z_\-]+", "_", asset_id).strip("_")
    clean_version = re.sub(r"[^0-9A-Za-z_\-]+", "_", version_no).strip("_") or "v1"
    return f"{prefix}_{clean_asset}_{clean_version}"


def _version_no(value: str | None, fallback: str = "v1") -> str:
    value = (value or "").strip()
    return value if value and value != "待确认" else fallback


def _policy_version_from_policy(policy: PolicyDocument, status: str = "current") -> PolicyVersion:
    version_no = _version_no(policy.version)
    version_id = policy.current_version_id or _safe_version_id("policy_version", policy.id, version_no)
    return PolicyVersion(
        id=version_id,
        policy_id=policy.id,
        version_no=version_no,
        effective_date=policy.effective_date,
        status=status,
        created_at=_now_iso(),
        change_summary="初始化当前版本",
        metadata={
            "name": policy.name,
            "code": policy.code,
            "category": policy.category,
            "org_scope": policy.org_scope,
            "status": policy.status,
        },
        clauses=policy.clauses,
        source_file=policy.source_file,
    )


def _process_version_from_process(process: ProcessDefinition, status: str = "current") -> ProcessVersion:
    version_no = _version_no(getattr(process, "version", None), "v1")
    version_id = process.current_version_id or _safe_version_id("process_version", process.id, version_no)
    return ProcessVersion(
        id=version_id,
        process_id=process.id,
        version_no=version_no,
        effective_date="当前生效",
        status=status,
        created_at=_now_iso(),
        change_summary="初始化当前版本",
        metadata={
            "name": process.name,
            "code": process.code,
            "business_domain": process.business_domain,
            "org_scope": process.org_scope,
            "status": process.status,
        },
        nodes=process.nodes,
        asset=process.asset,
    )


def reset_database() -> None:
    dataset = build_demo_dataset()
    policy_history: dict[str, list[PolicyVersion]] = {}
    for version in dataset.get("policy_version_history", []):
        policy_history.setdefault(version.policy_id, []).append(version)
    process_history: dict[str, list[ProcessVersion]] = {}
    for version in dataset.get("process_version_history", []):
        process_history.setdefault(version.process_id, []).append(version)
    with connect() as connection:
        init_schema(connection)
        for table in [
            "policies",
            "policy_versions",
            "processes",
            "process_versions",
            "knowledge_nodes",
            "knowledge_edges",
            "skills",
            "findings",
            "upload_sessions",
            "role_mappings",
        ]:
            connection.execute(f"DELETE FROM {table}")
        for item in dataset["policies"]:
            version = _policy_version_from_policy(item)
            item.current_version_id = version.id
            item.version_count = len(policy_history.get(item.id, [])) + 1
            connection.execute("INSERT INTO policies (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
            connection.execute(
                "INSERT INTO policy_versions (id, policy_id, payload) VALUES (?, ?, ?)",
                (version.id, item.id, _dump(version)),
            )
            for historical_version in policy_history.get(item.id, []):
                historical_version.status = "historical"
                connection.execute(
                    "INSERT INTO policy_versions (id, policy_id, payload) VALUES (?, ?, ?)",
                    (historical_version.id, historical_version.policy_id, _dump(historical_version)),
                )
        for item in dataset["processes"]:
            version = _process_version_from_process(item)
            item.current_version_id = version.id
            item.version_count = len(process_history.get(item.id, [])) + 1
            connection.execute("INSERT INTO processes (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
            connection.execute(
                "INSERT INTO process_versions (id, process_id, payload) VALUES (?, ?, ?)",
                (version.id, item.id, _dump(version)),
            )
            for historical_version in process_history.get(item.id, []):
                historical_version.status = "historical"
                connection.execute(
                    "INSERT INTO process_versions (id, process_id, payload) VALUES (?, ?, ?)",
                    (historical_version.id, historical_version.process_id, _dump(historical_version)),
                )
        for item in dataset["knowledge_nodes"]:
            connection.execute("INSERT INTO knowledge_nodes (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        for item in dataset["knowledge_edges"]:
            connection.execute("INSERT INTO knowledge_edges (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        connection.commit()


def ensure_database() -> None:
    with connect() as connection:
        init_schema(connection)
        count = connection.execute("SELECT COUNT(*) AS c FROM policies").fetchone()["c"]
        if count:
            _backfill_versions(connection)
    if count == 0:
        reset_database()


def _backfill_versions(connection: sqlite3.Connection) -> None:
    policy_rows = connection.execute("SELECT id, payload FROM policies").fetchall()
    for row in policy_rows:
        payload = _load(row)
        policy = PolicyDocument.model_validate(payload)
        existing_rows = connection.execute("SELECT payload FROM policy_versions WHERE policy_id = ?", (policy.id,)).fetchall()
        versions = [PolicyVersion.model_validate(_load(item)) for item in existing_rows]
        if not versions:
            version = _policy_version_from_policy(policy)
            policy.current_version_id = version.id
            policy.version_count = 1
            connection.execute(
                "INSERT INTO policy_versions (id, policy_id, payload) VALUES (?, ?, ?)",
                (version.id, policy.id, _dump(version)),
            )
            connection.execute("UPDATE policies SET payload = ? WHERE id = ?", (_dump(policy), policy.id))
        elif not policy.current_version_id or policy.version_count != len(versions):
            current = next((item for item in versions if item.status == "current"), versions[-1])
            policy.current_version_id = current.id
            policy.version_count = len(versions)
            connection.execute("UPDATE policies SET payload = ? WHERE id = ?", (_dump(policy), policy.id))

    process_rows = connection.execute("SELECT id, payload FROM processes").fetchall()
    for row in process_rows:
        payload = _load(row)
        process = ProcessDefinition.model_validate(payload)
        existing_rows = connection.execute("SELECT payload FROM process_versions WHERE process_id = ?", (process.id,)).fetchall()
        versions = [ProcessVersion.model_validate(_load(item)) for item in existing_rows]
        if not versions:
            version = _process_version_from_process(process)
            process.current_version_id = version.id
            process.version_count = 1
            connection.execute(
                "INSERT INTO process_versions (id, process_id, payload) VALUES (?, ?, ?)",
                (version.id, process.id, _dump(version)),
            )
            connection.execute("UPDATE processes SET payload = ? WHERE id = ?", (_dump(process), process.id))
        elif not process.current_version_id or process.version_count != len(versions):
            current = next((item for item in versions if item.status == "current"), versions[-1])
            process.current_version_id = current.id
            process.version_count = len(versions)
            connection.execute("UPDATE processes SET payload = ? WHERE id = ?", (_dump(process), process.id))
    connection.commit()


def fetch_all(table: str) -> list[dict]:
    ensure_database()
    with connect() as connection:
        rows = connection.execute(f"SELECT payload FROM {table}").fetchall()
    return [_load(row) for row in rows]


def fetch_one(table: str, item_id: str) -> dict | None:
    ensure_database()
    with connect() as connection:
        row = connection.execute(f"SELECT payload FROM {table} WHERE id = ?", (item_id,)).fetchone()
    return _load(row) if row else None


def delete_one(table: str, item_id: str) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        connection.commit()
    return cursor.rowcount > 0


def delete_policy(policy_id: str) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
        connection.execute("DELETE FROM policy_versions WHERE policy_id = ?", (policy_id,))
        connection.commit()
    return cursor.rowcount > 0


def delete_process(process_id: str) -> bool:
    ensure_database()
    with connect() as connection:
        cursor = connection.execute("DELETE FROM processes WHERE id = ?", (process_id,))
        connection.execute("DELETE FROM process_versions WHERE process_id = ?", (process_id,))
        connection.commit()
    return cursor.rowcount > 0


def insert_finding(finding: Finding) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO findings (id, skill_id, payload) VALUES (?, ?, ?)",
            (finding.id, finding.skill_id, _dump(finding)),
        )
        connection.commit()


def insert_policy(policy: PolicyDocument) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute("INSERT OR REPLACE INTO policies (id, payload) VALUES (?, ?)", (policy.id, _dump(policy)))
        connection.commit()


def fetch_policy_versions(policy_id: str) -> list[PolicyVersion]:
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM policy_versions WHERE policy_id = ?",
            (policy_id,),
        ).fetchall()
    versions = [PolicyVersion.model_validate(_load(row)) for row in rows]
    return sorted(versions, key=lambda item: (item.status != "current", item.created_at), reverse=False)


def fetch_policy_version(policy_id: str, version_id: str) -> PolicyVersion | None:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT payload FROM policy_versions WHERE policy_id = ? AND id = ?",
            (policy_id, version_id),
        ).fetchone()
    return PolicyVersion.model_validate(_load(row)) if row else None


def fetch_process_versions(process_id: str) -> list[ProcessVersion]:
    ensure_database()
    with connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM process_versions WHERE process_id = ?",
            (process_id,),
        ).fetchall()
    versions = [ProcessVersion.model_validate(_load(row)) for row in rows]
    return sorted(versions, key=lambda item: (item.status != "current", item.created_at), reverse=False)


def insert_current_policy_version(policy: PolicyDocument, change_summary: str = "") -> PolicyVersion:
    ensure_database()
    existing = fetch_policy_versions(policy.id)
    version_no = _version_no(policy.version, f"v{len(existing) + 1}")
    existing_ids = {item.id for item in existing}
    version_id = _safe_version_id("policy_version", policy.id, version_no)
    if version_id in existing_ids:
        version_id = _safe_version_id("policy_version", policy.id, f"{version_no}_rev{len(existing) + 1}")
    version = PolicyVersion(
        id=version_id,
        policy_id=policy.id,
        version_no=version_no,
        effective_date=policy.effective_date,
        status="current",
        created_at=_now_iso(),
        change_summary=change_summary or "上传新版本并默认生效",
        metadata={
            "name": policy.name,
            "code": policy.code,
            "category": policy.category,
            "org_scope": policy.org_scope,
            "status": policy.status,
        },
        clauses=policy.clauses,
        source_file=policy.source_file,
    )
    policy.current_version_id = version.id
    policy.version_count = len(existing) + 1
    with connect() as connection:
        for item in existing:
            item.status = "historical"
            connection.execute(
                "INSERT OR REPLACE INTO policy_versions (id, policy_id, payload) VALUES (?, ?, ?)",
                (item.id, item.policy_id, _dump(item)),
            )
        connection.execute(
            "INSERT OR REPLACE INTO policy_versions (id, policy_id, payload) VALUES (?, ?, ?)",
            (version.id, version.policy_id, _dump(version)),
        )
        connection.execute("INSERT OR REPLACE INTO policies (id, payload) VALUES (?, ?)", (policy.id, _dump(policy)))
        connection.commit()
    return version


def upsert_knowledge_node(node: KnowledgeNode) -> None:
    ensure_database()
    existing = fetch_one("knowledge_nodes", node.id)
    if existing:
        existing["source_count"] = int(existing.get("source_count", 1)) + node.source_count
        node = KnowledgeNode.model_validate(existing)
    with connect() as connection:
        connection.execute("INSERT OR REPLACE INTO knowledge_nodes (id, payload) VALUES (?, ?)", (node.id, _dump(node)))
        connection.commit()


def insert_upload_session(session_id: str, payload: dict) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute("INSERT OR REPLACE INTO upload_sessions (id, payload) VALUES (?, ?)", (session_id, _dump(payload)))
        connection.commit()


def upsert_role_mapping(mapping: RoleMapping) -> None:
    ensure_database()
    with connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO role_mappings (id, payload, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (mapping.id, _dump(mapping)),
        )
        connection.commit()


def fetch_role_mappings() -> list[RoleMapping]:
    return [RoleMapping.model_validate(item) for item in fetch_all("role_mappings")]


def get_upload_session(session_id: str) -> dict | None:
    return fetch_one("upload_sessions", session_id)


def update_finding_status(finding_id: str, status: str) -> Finding | None:
    existing = fetch_one("findings", finding_id)
    if not existing:
        return None
    existing["status"] = status
    if status == "closed":
        existing["closed_at"] = datetime.now(UTC).isoformat()
    else:
        existing["closed_at"] = None
    finding = Finding.model_validate(existing)
    insert_finding(finding)
    return finding


def fetch_findings() -> list[Finding]:
    findings = [Finding.model_validate(item) for item in fetch_all("findings")]
    current_policy_versions = {policy.current_version_id for policy in all_policies() if policy.current_version_id}
    current_process_versions = {process.current_version_id for process in all_processes() if process.current_version_id}
    for finding in findings:
        historical_policy = any(version_id and version_id not in current_policy_versions for version_id in finding.policy_version_ids)
        historical_process = any(version_id and version_id not in current_process_versions for version_id in finding.process_version_ids)
        finding.based_on_historical_version = historical_policy or historical_process
    return findings


def all_policies() -> list[PolicyDocument]:
    return [PolicyDocument.model_validate(item) for item in fetch_all("policies")]


def all_processes() -> list[ProcessDefinition]:
    return [ProcessDefinition.model_validate(item) for item in fetch_all("processes")]


def selected_policies(ids: Iterable[str]) -> list[PolicyDocument]:
    id_set = set(ids)
    return [policy for policy in all_policies() if policy.id in id_set]


def selected_processes(ids: Iterable[str]) -> list[ProcessDefinition]:
    id_set = set(ids)
    return [process for process in all_processes() if process.id in id_set]
