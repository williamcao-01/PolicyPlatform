from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

KG_TYPE_ALIASES = {
    "Role": "人员角色",
    "角色": "人员角色",
    "人员角色": "人员角色",
    "岗位": "人员角色",
    "Position": "人员角色",
    "Department": "部门组织",
    "部门": "部门组织",
    "组织": "部门组织",
    "组织部门": "部门组织",
    "部门组织": "部门组织",
    "Organization": "部门组织",
    "OrgUnit": "部门组织",
    "BusinessRule": "业务规则",
    "Rule": "业务规则",
    "业务规则": "业务规则",
    "规则": "业务规则",
    "Condition": "业务规则",
}


def safe_upload_id(prefix: str, text: str | None = None) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]+", "_", text or "")[:32].strip("_").lower()
    random_part = uuid4().hex[:8]
    return f"{prefix}_{suffix}_{random_part}" if suffix else f"{prefix}_{random_part}"


async def extract_upload_text(file: UploadFile) -> str:
    data = await file.read()
    return extract_upload_text_from_bytes(data, file.filename or "")


def extract_upload_text_from_bytes(data: bytes, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        temp_path = Path("backend") / f"upload_{uuid4().hex}.pdf"
        temp_path.write_bytes(data)
        try:
            reader = PdfReader(str(temp_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        finally:
            temp_path.unlink(missing_ok=True)
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="ignore")
    raise ValueError("当前仅支持 PDF、TXT、Markdown 文件。")


def split_policy_clauses(text: str, policy_id: str) -> list[dict[str, Any]]:
    lines = _policy_body_lines(text)
    clauses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    index_by_clause_no: dict[str, str] = {}
    latest_by_level: dict[int, str] = {}

    def append_current() -> None:
        if current and current["content"].strip():
            clauses.append(current)

    def parent_for_heading(heading: dict[str, Any]) -> str | None:
        explicit_parent_no = heading.get("parent_no")
        if explicit_parent_no:
            return index_by_clause_no.get(explicit_parent_no)
        level = int(heading["level"])
        for candidate_level in range(level - 1, 0, -1):
            parent_id = latest_by_level.get(candidate_level)
            if parent_id:
                return parent_id
        return None

    def start_clause(heading: dict[str, Any], line: str) -> None:
        nonlocal current
        append_current()
        clause_no = str(heading["clause_no"])
        clause_id = f"clause_{policy_id}_{len(clauses) + 1}"
        current = {
            "id": clause_id,
            "policy_id": policy_id,
            "clause_no": clause_no,
            "title": str(heading["title"])[:80] or f"条款 {clause_no}",
            "content": line,
            "parent_id": parent_for_heading(heading),
            "order_index": len(clauses) + 1,
        }
        index_by_clause_no[clause_no] = clause_id
        level = int(heading["level"])
        latest_by_level[level] = clause_id
        for stale_level in [item for item in latest_by_level if item > level]:
            del latest_by_level[stale_level]

    for line in lines:
        heading = _detect_heading(line, latest_by_level, index_by_clause_no)
        if heading:
            start_clause(heading, line)
        elif current:
            current["content"] = f"{current['content']}\n{line}"
    if current:
        clauses.append(current)
    return clauses[:160]


def _detect_heading(line: str, latest_by_level: dict[int, str], index_by_clause_no: dict[str, str]) -> dict[str, Any] | None:
    markdown_match = re.match(r"^(?P<marks>#{1,6})\s+(?P<title>.+)$", line)
    if markdown_match:
        level = len(markdown_match.group("marks"))
        return {"clause_no": f"H{level}-{len(index_by_clause_no) + 1}", "title": markdown_match.group("title").strip(), "level": level}

    chapter_match = re.match(r"^第(?P<num>[\d一二三四五六七八九十百千万]+)章[ 　]*(?P<title>.*)$", line)
    if chapter_match:
        clause_no = f"第{chapter_match.group('num')}章"
        return {"clause_no": clause_no, "title": chapter_match.group("title").strip(), "level": 1}

    section_match = re.match(r"^第(?P<num>[\d一二三四五六七八九十百千万]+)节[ 　]*(?P<title>.*)$", line)
    if section_match:
        clause_no = f"第{section_match.group('num')}节"
        return {"clause_no": clause_no, "title": section_match.group("title").strip(), "level": 2}

    article_match = re.match(r"^第(?P<num>[\d一二三四五六七八九十百千万]+)条[ 　]*(?P<title>.*)$", line)
    if article_match:
        clause_no = f"第{article_match.group('num')}条"
        return {"clause_no": clause_no, "title": article_match.group("title").strip(), "level": _article_level(latest_by_level, index_by_clause_no)}

    numeric_match = re.match(r"^(?P<num>\d+(?:\.\d+){0,5})(?:\s+|[、.．])(?P<title>.+)?$", line)
    if numeric_match:
        clause_no = numeric_match.group("num")
        return {
            "clause_no": clause_no,
            "title": (numeric_match.group("title") or "").strip(),
            "level": clause_no.count(".") + 1,
            "parent_no": ".".join(clause_no.split(".")[:-1]) if "." in clause_no else None,
        }

    chinese_list_match = re.match(r"^(?P<num>[一二三四五六七八九十]+)[、.．]\s*(?P<title>.+)$", line)
    if chinese_list_match:
        clause_no = chinese_list_match.group("num")
        return {"clause_no": clause_no, "title": chinese_list_match.group("title").strip(), "level": 1}

    parenthetical_match = re.match(r"^[（(](?P<num>\d+|[一二三四五六七八九十]+)[）)]\s*(?P<title>.+)$", line)
    if parenthetical_match:
        raw_no = parenthetical_match.group("num")
        parent_level, parent_no = _deepest_parent(latest_by_level, index_by_clause_no, raw_no)
        clause_no = f"{parent_no}({raw_no})" if parent_no else f"({raw_no})"
        return {
            "clause_no": clause_no,
            "title": parenthetical_match.group("title").strip(),
            "level": parent_level + 1 if parent_level else 1,
            "parent_no": parent_no,
        }

    return None


def _article_level(latest_by_level: dict[int, str], index_by_clause_no: dict[str, str]) -> int:
    id_to_clause_no = {value: key for key, value in index_by_clause_no.items()}
    if 2 in latest_by_level and "节" in id_to_clause_no.get(latest_by_level[2], ""):
        return 3
    if 1 in latest_by_level and "章" in id_to_clause_no.get(latest_by_level[1], ""):
        return 2
    return 1


def _deepest_parent(latest_by_level: dict[int, str], index_by_clause_no: dict[str, str], current_parenthetical_no: str) -> tuple[int | None, str | None]:
    if not latest_by_level:
        return None, None
    id_to_clause_no = {value: key for key, value in index_by_clause_no.items()}
    for level in sorted(latest_by_level, reverse=True):
        parent_no = id_to_clause_no.get(latest_by_level[level])
        if parent_no:
            sibling_parent = _sibling_parent_for_parenthetical(parent_no, current_parenthetical_no)
            if sibling_parent:
                return level - 1, sibling_parent
            return level, parent_no
    return None, None


def _sibling_parent_for_parenthetical(previous_clause_no: str, current_parenthetical_no: str) -> str | None:
    match = re.match(r"^(?P<parent>.+)\((?P<num>\d+|[一二三四五六七八九十]+)\)$", previous_clause_no)
    if not match:
        return None
    previous_num = match.group("num")
    if previous_num.isdigit() == current_parenthetical_no.isdigit():
        return match.group("parent")
    return None


def extract_policy_metadata(text: str) -> dict[str, str]:
    first_body_lines = _policy_body_lines(text)[:30]
    first_lines = "\n".join(first_body_lines)
    name = _extract_policy_name(first_body_lines)
    code_match = re.search(r"(?:编号|制度编号)\s*([A-Z0-9.\-]+)", first_lines)
    version_match = re.search(r"(?:版本|版号)\s*([A-Za-z0-9/.\-]+)", first_lines)
    date_match = re.search(r"(?:生效日期|发布日期)\s*([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})", first_lines)
    module_match = re.search(r"(?:所属模块|模块|类别)\s*([^\s\n]+)", first_lines)
    return {
        "name": name,
        "code": code_match.group(1).strip() if code_match else "",
        "version": version_match.group(1).strip() if version_match else "",
        "effective_date": date_match.group(1).replace("/", "-") if date_match else "",
        "category": module_match.group(1).strip() if module_match else "",
        "org_scope": "待确认",
    }


def _extract_policy_name(lines: list[str]) -> str:
    policy_keywords = ("制度", "办法", "细则", "指引", "规范", "规定", "规程")
    blocked_prefixes = ("编号", "制度编号", "版本", "版号", "生效日期", "发布日期", "所属模块", "模块", "类别")
    candidates: list[str] = []
    for index, line in enumerate(lines[:20]):
        normalized = re.sub(r"\s+", "", line).strip(" ：:")
        if not normalized or normalized.startswith(blocked_prefixes):
            continue
        joined_with_next = ""
        if index + 1 < len(lines):
            joined_with_next = re.sub(r"\s+", "", line + lines[index + 1]).strip(" ：:")
        for candidate in [normalized, joined_with_next]:
            if 4 <= len(candidate) <= 120 and candidate.endswith(policy_keywords):
                candidates.append(candidate)
    if candidates:
        return max(candidates, key=len)
    first_lines = "\n".join(lines[:20])
    name_match = re.search(r"(?:文件名\s*)?([^\n]{4,100}(?:制度|办法|细则|指引|规范|规定|规程))", first_lines)
    return name_match.group(1).strip() if name_match else "未命名制度"


def extract_policy_concepts(text: str) -> list[dict[str, str]]:
    candidates = {
        "人员角色": ["采购中心", "采购管理部门", "采购实施部门", "决策小组", "风控", "人力资源负责人", "分管领导", "平台公司业务分管领导", "部门负责人", "平台总经理", "子公司总经理"],
        "部门组织": ["生产管理中心", "生产管理部", "饲料产品部", "饲料厂", "财务运营部", "数字化部", "下属企业"],
    }
    concepts = []
    for node_type, terms in candidates.items():
        for term in terms:
            if term in text:
                concepts.append({"node_type": node_type, "name": term})
    for match in re.finditer(r"(?:金额|单笔金额|采购金额)?超过\s*\d+\s*万元[^。；\n]{0,40}(?:审批|复核|备案|决策)", text):
        concepts.append({"node_type": "业务规则", "name": match.group(0).strip("，；。 ")})
    for match in re.finditer(r"[^。；\n]{0,30}(?:需|应|必须|不得)[^。；\n]{0,50}(?:审批|复核|备案|决策|记录|归档)", text):
        rule = match.group(0).strip("，；。 ")
        if 6 <= len(rule) <= 80:
            concepts.append({"node_type": "业务规则", "name": rule})
    return filter_policy_concepts(concepts)


def filter_policy_concepts(concepts: list[dict[str, Any]]) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for concept in concepts:
        node_type = KG_TYPE_ALIASES.get(str(concept.get("node_type", "")).strip())
        name = str(concept.get("name", "")).strip()
        if not node_type or not name:
            continue
        if len(name) > 100:
            continue
        key = (node_type, name)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"node_type": node_type, "name": name})
    return filtered


def _policy_body_lines(text: str) -> list[str]:
    lines: list[str] = []
    in_attachment = False
    skip_patterns = [
        re.compile(r"^文件名\s+"),
        re.compile(r"^编号\s+.+页码\s+"),
        re.compile(r"^编制\s+.+生效日期\s+.+页码\s+"),
        re.compile(r"^第\s*\d+\s*页[，,]\s*共\s*\d+\s*页$"),
    ]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^附件(?:\s*[一二三四五六七八九十\d]+)?[：:、.\s]", line) or line == "附件":
            in_attachment = True
            continue
        if in_attachment:
            continue
        if any(pattern.search(line) for pattern in skip_patterns):
            continue
        lines.append(line)
    return lines
