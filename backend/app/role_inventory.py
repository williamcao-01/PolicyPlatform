from __future__ import annotations

import json
import re
from collections import defaultdict

from pydantic import BaseModel

from app import db
from app.deepseek_client import DeepSeekClient, load_deepseek_settings
from app.models import RoleEntry, RoleInventory, RoleMapping, RoleMention


ROLE_SUFFIXES = (
    "董事长",
    "总经理",
    "负责人",
    "分管领导",
    "领导",
    "专员",
    "经理",
    "主管",
    "主任",
    "采购部",
    "人力资源部",
    "生产管理中心",
    "饲料产品部",
    "饲料厂",
    "采购中心",
    "管理部门",
    "实施部门",
    "用人部门",
    "决策小组",
    "委员会",
    "办公室",
    "中心",
    "部门",
    "小组",
)

ROLE_PATTERN = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]{2,28}(?:" + "|".join(re.escape(item) for item in ROLE_SUFFIXES) + r")")
NOISE_PREFIXES = ("由", "经", "报", "向", "及", "和", "与", "对", "为", "由各", "各", "公司")
GENERIC_ROLES = {"公司", "部门", "中心", "小组", "负责人", "领导", "制度", "流程", "本制度"}
ACTION_PREFIXES = (
    "负责对",
    "负责",
    "协调解决",
    "指导",
    "参与外购",
    "参与",
    "组织",
    "结合",
    "统计分析",
    "确认中选前",
    "岗位编制依据",
    "报告",
    "告",
)
CANONICAL_TERMS = (
    "平台公司业务分管领导",
    "饲料原料采购决策小组",
    "生产管理中心",
    "采购管理部门",
    "采购实施部门",
    "用人部门负责人",
    "人力资源负责人",
    "采购部门负责人",
    "平台总经理",
    "平台董事长",
    "子公司总经理",
    "平台采购部",
    "采购中心",
    "决策小组",
    "分管领导",
    "部门负责人",
    "生产负责人",
    "薪酬负责人",
    "人力专员",
    "下属饲料厂",
    "饲料产品部",
    "饲料厂",
)


class RoleMappingUpdate(BaseModel):
    policy_role: str
    process_role: str
    status: str = "mapped"


def role_inventory() -> RoleInventory:
    policy_roles = _extract_policy_roles()
    process_roles = _extract_process_roles()
    mappings = _merge_manual_mappings(
        _auto_mappings_with_llm_fallback(policy_roles, process_roles),
        db.fetch_role_mappings(),
        {role.name for role in policy_roles},
        {role.name for role in process_roles},
    )
    return RoleInventory(policy_roles=policy_roles, process_roles=process_roles, mappings=mappings)


def save_manual_mapping(payload: RoleMappingUpdate) -> RoleMapping:
    mapping = RoleMapping(
        id=_mapping_id(payload.policy_role, payload.process_role),
        policy_role=payload.policy_role,
        process_role=payload.process_role,
        confidence=1.0,
        mapping_type="manual",
        status=payload.status if payload.status in {"mapped", "unmapped", "ignored"} else "mapped",
        rationale="人工调整的制度角色与审批角色映射。",
    )
    db.upsert_role_mapping(mapping)
    return mapping


def role_count() -> int:
    names = {role.name for role in _extract_policy_roles()} | {role.name for role in _extract_process_roles()}
    return len(names)


def _extract_policy_roles() -> list[RoleEntry]:
    roles: dict[str, list[RoleMention]] = defaultdict(list)
    process_role_names = {node.role for process in db.all_processes() for node in process.nodes if node.role}

    for policy in db.all_policies():
        for clause in policy.clauses:
            text = f"{clause.title}。{clause.content}"
            candidates = set(_extract_role_names(text))
            candidates.update(role for role in process_role_names if role and role in text)
            for name in sorted(candidates):
                roles[name].append(
                    RoleMention(
                        asset_id=policy.id,
                        asset_name=policy.name,
                        item_id=clause.id,
                        item_label=f"{clause.clause_no} {clause.title}".strip(),
                        quote=_quote(text, name),
                    )
                )

    return [
        RoleEntry(id=_safe_id("policy_role", name), name=name, source="policy", mention_count=len(mentions), mentions=mentions)
        for name, mentions in sorted(roles.items(), key=lambda item: (-len(item[1]), item[0]))
    ]


def _extract_process_roles() -> list[RoleEntry]:
    roles: dict[str, list[RoleMention]] = defaultdict(list)
    for process in db.all_processes():
        for node in process.nodes:
            if not node.role:
                continue
            roles[node.role].append(
                RoleMention(
                    asset_id=process.id,
                    asset_name=process.name,
                    item_id=node.id,
                    item_label=f"{node.order_index}. {node.name}",
                    quote=f"{node.name} / {node.action}" + (f" / {node.condition}" if node.condition else ""),
                )
            )

    return [
        RoleEntry(id=_safe_id("process_role", name), name=name, source="process", mention_count=len(mentions), mentions=mentions)
        for name, mentions in sorted(roles.items(), key=lambda item: (-len(item[1]), item[0]))
    ]


def _extract_role_names(text: str) -> list[str]:
    names = set()
    for raw in ROLE_PATTERN.findall(text):
        name = _normalize_role(raw)
        if name and name not in GENERIC_ROLES and len(name) <= 18:
            names.add(name)
    return sorted(names)


def _normalize_role(name: str) -> str:
    name = re.sub(r"[，。；：、（）()《》“”\"' \t\r\n]+", "", name)
    for marker in ("交由", "提交", "上报", "报", "由", "经", "向"):
        if marker in name and len(name.rsplit(marker, 1)[-1]) >= 2:
            name = name.rsplit(marker, 1)[-1]
    for prefix in NOISE_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix) + 1:
            name = name[len(prefix) :]
    for prefix in ACTION_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix) + 1:
            name = name[len(prefix) :]
    for term in CANONICAL_TERMS:
        if term in name and name != term:
            return term
    return name


def _auto_mappings_with_llm_fallback(policy_roles: list[RoleEntry], process_roles: list[RoleEntry]) -> list[RoleMapping]:
    settings = load_deepseek_settings()
    if settings.use_real_llm and settings.api_key and policy_roles and process_roles:
        try:
            return _llm_mappings(policy_roles, process_roles)
        except Exception:
            return _deterministic_mappings(policy_roles, process_roles, "DeepSeek 映射失败，已使用本地相似度规则生成候选。")
    return _deterministic_mappings(policy_roles, process_roles, "未启用真实大模型，已使用本地相似度规则生成候选。")


def _llm_mappings(policy_roles: list[RoleEntry], process_roles: list[RoleEntry]) -> list[RoleMapping]:
    policy_names = [role.name for role in policy_roles]
    process_names = [role.name for role in process_roles]
    result = DeepSeekClient().chat_json(
        "你是制度与BPMN审批流角色映射专家。只输出合法JSON，不要解释。",
        (
            "请把制度角色映射到最可能对应的审批流角色。"
            "只能使用给定列表里的名称；不确定时不要强行映射。"
            "输出格式：{\"mappings\":[{\"policy_role\":\"...\",\"process_role\":\"...\",\"confidence\":0.0,\"rationale\":\"...\"}]}\n"
            f"制度角色：{json.dumps(policy_names, ensure_ascii=False)}\n"
            f"审批流角色：{json.dumps(process_names, ensure_ascii=False)}"
        ),
    )
    valid_policy = set(policy_names)
    valid_process = set(process_names)
    mappings = []
    for item in result.get("mappings", []):
        policy_role = str(item.get("policy_role", "")).strip()
        process_role = str(item.get("process_role", "")).strip()
        if policy_role not in valid_policy or process_role not in valid_process:
            continue
        mappings.append(
            RoleMapping(
                id=_mapping_id(policy_role, process_role),
                policy_role=policy_role,
                process_role=process_role,
                confidence=max(0.0, min(float(item.get("confidence", 0.0)), 1.0)),
                mapping_type="auto",
                status="mapped",
                rationale=str(item.get("rationale", "DeepSeek 根据角色名称和职责语义生成的映射建议。")),
            )
        )
    return mappings or _deterministic_mappings(policy_roles, process_roles, "DeepSeek 未返回有效映射，已使用本地相似度规则生成候选。")


def _deterministic_mappings(policy_roles: list[RoleEntry], process_roles: list[RoleEntry], rationale_suffix: str) -> list[RoleMapping]:
    mappings = []
    process_names = [role.name for role in process_roles]
    for policy_role in policy_roles:
        best_name = ""
        best_score = 0.0
        for process_name in process_names:
            score = _role_similarity(policy_role.name, process_name)
            if score > best_score:
                best_name = process_name
                best_score = score
        if best_name and best_score >= 0.52:
            mappings.append(
                RoleMapping(
                    id=_mapping_id(policy_role.name, best_name),
                    policy_role=policy_role.name,
                    process_role=best_name,
                    confidence=round(best_score, 2),
                    mapping_type="auto",
                    status="mapped",
                    rationale=rationale_suffix,
                )
            )
    return mappings


def _role_similarity(policy_role: str, process_role: str) -> float:
    if policy_role == process_role:
        return 0.98
    if policy_role in process_role or process_role in policy_role:
        return 0.82
    policy_chars = set(policy_role)
    process_chars = set(process_role)
    overlap = len(policy_chars & process_chars) / max(len(policy_chars | process_chars), 1)
    suffix_bonus = 0.16 if policy_role[-2:] == process_role[-2:] else 0.0
    return min(overlap + suffix_bonus, 0.78)


def _merge_manual_mappings(
    auto_mappings: list[RoleMapping],
    manual_mappings: list[RoleMapping],
    policy_roles: set[str],
    process_roles: set[str],
) -> list[RoleMapping]:
    manual_mappings = [
        mapping for mapping in manual_mappings if mapping.policy_role in policy_roles and mapping.process_role in process_roles
    ]
    manual_pairs = {(mapping.policy_role, mapping.process_role) for mapping in manual_mappings}
    merged = [mapping for mapping in auto_mappings if (mapping.policy_role, mapping.process_role) not in manual_pairs]
    merged.extend(manual_mappings)
    return sorted(merged, key=lambda item: (item.mapping_type != "manual", item.policy_role, -item.confidence))


def _quote(text: str, term: str) -> str:
    index = text.find(term)
    if index < 0:
        return text[:90]
    start = max(0, index - 28)
    end = min(len(text), index + len(term) + 42)
    return text[start:end]


def _safe_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+", "_", value).strip("_")
    return f"{prefix}_{slug}"


def _mapping_id(policy_role: str, process_role: str) -> str:
    return _safe_id("role_mapping", f"{policy_role}_{process_role}")
