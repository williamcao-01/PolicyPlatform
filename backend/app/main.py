from __future__ import annotations

import json

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app import db
from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.audit import router as audit_router
from app.api.ai_governance import router as ai_governance_router
from app.api.dependencies import require_permission_legacy
from app.api.errors import app_error_handler
from app.api.tasks import router as tasks_router
from app.api.system_settings import router as system_settings_router
from app.core.exceptions import AppError
from app.core.permissions import Permission
from app.deepseek_client import load_deepseek_settings
from app.excel_export import findings_workbook
from app.hooks import hooks
from app.knowledge_base import KnowledgeBaseClient, load_knowledge_base_settings, professional_references_from_kb
from pydantic import BaseModel

from app.models import DashboardSummary, ProfessionalReference, RoleInventory, RoleMapping, SkillRunRequest, SkillRunResult
from app.policy_upload import (
    analyze_policy_text,
    extract_upload_text_from_bytes,
    save_policy_analysis,
    source_file_for_analysis,
    source_file_for_policy,
    source_file_for_policy_version,
)
from app.role_inventory import RoleMappingUpdate, role_inventory, save_manual_mapping
from app.skill_runner import run_skill as execute_skill
from app.store import store

app = FastAPI(title="AI 制度管理 Demo API")
app.add_exception_handler(AppError, app_error_handler)


class FindingStatusUpdate(BaseModel):
    status: str


class UploadSaveRequest(BaseModel):
    category: str
    answers: dict[str, str] = {}


class ProfessionalReferenceExplainRequest(BaseModel):
    reference: ProfessionalReference
    question: str = ""
    context: str = ""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(tasks_router)
app.include_router(assets_router)
app.include_router(ai_governance_router)
app.include_router(system_settings_router)


@app.get("/api/health")
def health() -> dict:
    settings = load_deepseek_settings()
    kb_settings = load_knowledge_base_settings()
    return {
        "status": "ok",
        "llm_mode": "real" if settings.use_real_llm else "mock",
        "deepseek_base_url": settings.base_url,
        "deepseek_model": settings.model,
        "has_deepseek_key": bool(settings.api_key),
        "knowledge_base_enabled": kb_settings.enabled,
        "knowledge_api_url": kb_settings.api_url,
    }


@app.post("/api/seed/reset")
def reset_seed() -> dict:
    store.reset()
    hooks.clear()
    return {"status": "reset"}


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> dict:
    return store.dashboard_summary()


@app.get("/api/policies")
def policies() -> list:
    return store.all("policies")


@app.get("/api/policies/tree")
def policy_tree() -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for policy in store.all("policies"):
        groups.setdefault(policy.category, []).append(
            {
                "key": policy.id,
                "title": policy.name,
                "type": "policy",
                "children": [],
            }
        )
    return [
        {"key": f"category_{category}", "title": category, "type": "category", "children": children}
        for category, children in groups.items()
    ]


@app.get("/api/policies/{policy_id}")
def policy_detail(policy_id: str):
    policy = store.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.get("/api/policies/{policy_id}/versions")
def policy_versions(policy_id: str) -> list:
    if not store.get_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    return db.fetch_policy_versions(policy_id)


@app.delete("/api/policies/{policy_id}")
def delete_policy(
    policy_id: str,
    _=Depends(require_permission_legacy(Permission.ASSET_ARCHIVE)),
) -> dict:
    if not store.delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"status": "deleted", "policy_id": policy_id}


@app.get("/api/processes")
def processes() -> list:
    return store.all("processes")


@app.get("/api/processes/tree")
def process_tree() -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for process in store.all("processes"):
        groups.setdefault(process.business_domain, []).append(
            {"key": process.id, "title": process.asset.file_name, "type": "process"}
        )
    return [
        {"key": f"process_domain_{domain}", "title": domain, "type": "domain", "children": children}
        for domain, children in groups.items()
    ]


@app.get("/api/processes/{process_id}")
def process_detail(process_id: str):
    process = store.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


@app.get("/api/processes/{process_id}/versions")
def process_versions(process_id: str) -> list:
    if not store.get_process(process_id):
        raise HTTPException(status_code=404, detail="Process not found")
    return db.fetch_process_versions(process_id)


@app.delete("/api/processes/{process_id}")
def delete_process(
    process_id: str,
    _=Depends(require_permission_legacy(Permission.ASSET_ARCHIVE)),
) -> dict:
    if not store.delete_process(process_id):
        raise HTTPException(status_code=404, detail="Process not found")
    return {"status": "deleted", "process_id": process_id}


@app.get("/api/processes/{process_id}/bpmn")
def process_bpmn(process_id: str) -> dict:
    process = store.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return {"process_id": process.id, "file_name": process.asset.file_name, "bpmn_xml": process.asset.bpmn_xml}


@app.get("/api/knowledge-graph")
def knowledge_graph() -> dict:
    return {"nodes": store.all("knowledge_nodes"), "edges": store.all("knowledge_edges")}


@app.get("/api/roles", response_model=RoleInventory)
def roles() -> RoleInventory:
    return role_inventory()


@app.post("/api/role-mappings", response_model=RoleMapping)
def update_role_mapping(payload: RoleMappingUpdate) -> RoleMapping:
    return save_manual_mapping(payload)


@app.get("/api/skills")
def skills() -> list:
    return store.all("skills")


@app.post("/api/policy-uploads/analyze")
async def analyze_policy_upload(
    file: UploadFile = File(...),
    _=Depends(require_permission_legacy(Permission.ASSET_CREATE)),
) -> dict:
    try:
        data = await file.read()
        file_name = file.filename or "uploaded-policy"
        text = extract_upload_text_from_bytes(data, file_name)
        return analyze_policy_text(text, file_name, data, file.content_type or "application/octet-stream")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/policy-uploads/{analysis_id}/source")
def download_upload_source(analysis_id: str):
    try:
        path, source = source_file_for_analysis(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    return FileResponse(path, media_type=source.get("content_type") or "application/octet-stream", filename=source.get("file_name") or path.name)


@app.post("/api/policy-uploads/{analysis_id}/save")
def save_policy_upload(
    analysis_id: str,
    payload: UploadSaveRequest,
    _=Depends(require_permission_legacy(Permission.ASSET_CREATE)),
):
    try:
        return save_policy_analysis(analysis_id, payload.category, payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/policies/{policy_id}/source")
def download_policy_source(policy_id: str):
    policy = store.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    try:
        path, source = source_file_for_policy(policy)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    return FileResponse(path, media_type=source.get("content_type") or "application/octet-stream", filename=source.get("file_name") or path.name)


@app.get("/api/policies/{policy_id}/versions/{version_id}/source")
def download_policy_version_source(policy_id: str, version_id: str):
    try:
        path, source = source_file_for_policy_version(policy_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    return FileResponse(path, media_type=source.get("content_type") or "application/octet-stream", filename=source.get("file_name") or path.name)


@app.get("/api/findings")
def findings() -> list:
    return store.all("findings")


@app.get("/api/exports/findings.xlsx")
def export_findings() -> Response:
    content = findings_workbook(store.all("findings"))
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="pending-risks.xlsx"'},
    )


@app.patch("/api/findings/{finding_id}")
def update_finding(
    finding_id: str,
    payload: FindingStatusUpdate,
    _=Depends(require_permission_legacy(Permission.FINDING_UPDATE)),
):
    finding = store.update_finding_status(finding_id, payload.status)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


@app.post("/api/skill-runs", response_model=SkillRunResult)
def run_skill(
    request: SkillRunRequest,
    _=Depends(require_permission_legacy(Permission.SKILL_RUN)),
) -> SkillRunResult:
    return execute_skill(request)


@app.post("/api/professional-references/explain", response_model=ProfessionalReference)
def explain_professional_reference(payload: ProfessionalReferenceExplainRequest) -> ProfessionalReference:
    reference = payload.reference
    question = (
        "请基于资产库检索结果，解释这个引用依据在本次制度/审批流核验中如何影响判断。"
        "必须返回命中的具体内容、该内容支持了什么专业判断、它不能替代哪些制度/BPMN原文证据。"
    )
    context = json.dumps(
        {
            "current_question": payload.question,
            "current_context": payload.context,
            "reference": reference.model_dump(),
        },
        ensure_ascii=False,
    )
    data = KnowledgeBaseClient().ask(question=question, context=context, limit=4)
    enriched = professional_references_from_kb(data, limit=1)
    if enriched:
        hit = enriched[0]
        reference.hit_content = hit.hit_content or hit.snippet or reference.hit_content or reference.snippet
        reference.impact = _compact_reference_answer(str(data.get("answer") or hit.impact or reference.impact))
        reference.confidence = hit.confidence or reference.confidence
        if not reference.snippet:
            reference.snippet = hit.snippet
    elif data.get("answer"):
        reference.impact = str(data.get("answer"))
    if not reference.hit_content:
        reference.hit_content = reference.snippet
    if not reference.impact:
        reference.impact = "该依据用于提供专业判断框架；正式风险结论仍以制度条款和 BPMN 节点证据为准。"
    return reference


def _compact_reference_answer(answer: str) -> str:
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    useful: list[str] = []
    capture = False
    for line in lines:
        if line.startswith("## References"):
            break
        if line.startswith("## 直接回答") or line.startswith("## 知识展开") or line.startswith("## 咨询使用方式"):
            capture = True
            continue
        if line.startswith("## "):
            capture = False
            continue
        if capture and not line.startswith("- 我把这个问题识别为"):
            useful.append(line)
    compact = " ".join(useful) or " ".join(lines)
    return compact[:900] + ("..." if len(compact) > 900 else "")


@app.get("/api/hooks/events")
def hook_events(
    _=Depends(require_permission_legacy(Permission.SKILL_AUDIT_READ)),
) -> list:
    return hooks.events
