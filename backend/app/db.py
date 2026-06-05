from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.data.demo_seed import build_demo_dataset
from app.models import Evidence, Finding, KnowledgeNode, PolicyDocument, ProcessDefinition, RoleMapping


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
        CREATE TABLE IF NOT EXISTS processes (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
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


def reset_database() -> None:
    dataset = build_demo_dataset()
    with connect() as connection:
        init_schema(connection)
        for table in [
            "policies",
            "processes",
            "knowledge_nodes",
            "knowledge_edges",
            "skills",
            "findings",
            "upload_sessions",
            "role_mappings",
        ]:
            connection.execute(f"DELETE FROM {table}")
        for item in dataset["policies"]:
            connection.execute("INSERT INTO policies (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        for item in dataset["processes"]:
            connection.execute("INSERT INTO processes (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        for item in dataset["knowledge_nodes"]:
            connection.execute("INSERT INTO knowledge_nodes (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        for item in dataset["knowledge_edges"]:
            connection.execute("INSERT INTO knowledge_edges (id, payload) VALUES (?, ?)", (item.id, _dump(item)))
        connection.commit()


def ensure_database() -> None:
    with connect() as connection:
        init_schema(connection)
        count = connection.execute("SELECT COUNT(*) AS c FROM policies").fetchone()["c"]
    if count == 0:
        reset_database()


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
    return [Finding.model_validate(item) for item in fetch_all("findings")]


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
