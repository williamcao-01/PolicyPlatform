import os
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services.system_settings import system_settings_service


client = TestClient(app)
KB_UNAVAILABLE_Q = "专业知识库当前不可用。是否允许本次仅基于制度和流程证据先生成待复核结论？"


def setup_function() -> None:
    os.environ["KNOWLEDGE_API_URL"] = "http://127.0.0.1:9"
    os.environ["KNOWLEDGE_BASE_ENABLED"] = "true"
    os.environ["USE_REAL_LLM"] = "false"
    system_settings_service.reset_from_environment()


def test_dashboard_summary_counts_seed_assets() -> None:
    client.post("/api/seed/reset")
    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["policy_count"] == 12
    assert body["process_count"] == 10
    assert body["finding_count"] == 0


def test_skill_run_emits_hook_events() -> None:
    client.post("/api/seed/reset")
    pause_response = client.post(
        "/api/skill-runs",
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
            "process_ids": [],
            "knowledge_node_ids": [],
        },
    )
    pause_body = pause_response.json()
    assert pause_body["findings"] == []
    assert pause_body["questions"]
    assert "确认前不会输出风险结论" in pause_body["final_answer"]

    response = client.post(
        "/api/skill-runs",
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
            "process_ids": [],
            "knowledge_node_ids": [],
            "clarification_answers": {KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["findings"][0]["finding_type"] == "policy_conflict"

    events = client.get("/api/hooks/events").json()
    event_names = [event["name"] for event in events]
    assert "before_skill_run" in event_names
    assert "finding_created" in event_names
    assert "evidence_attached" in event_names
    assert "after_skill_run" in event_names


def test_upload_policy_skill_is_registered() -> None:
    response = client.get("/api/skills")

    assert response.status_code == 200
    skill_ids = {item["id"] for item in response.json()}
    assert "skill_upload_policy_file" in skill_ids


def test_role_inventory_and_manual_mapping() -> None:
    client.post("/api/seed/reset")
    response = client.get("/api/roles")

    assert response.status_code == 200
    body = response.json()
    assert body["policy_roles"]
    assert body["process_roles"]
    assert any(role["name"] == "平台总经理" for role in body["process_roles"])

    mapping_response = client.post(
        "/api/role-mappings",
        json={"policy_role": body["policy_roles"][0]["name"], "process_role": "平台总经理"},
    )

    assert mapping_response.status_code == 200
    assert mapping_response.json()["mapping_type"] == "manual"

    refreshed = client.get("/api/roles").json()
    assert any(mapping["mapping_type"] == "manual" for mapping in refreshed["mappings"])


def test_delete_policy_and_process() -> None:
    client.post("/api/seed/reset")

    policy_response = client.delete("/api/policies/policy_purchase")
    assert policy_response.status_code == 200
    assert client.get("/api/policies/policy_purchase").status_code == 404
    summary = client.get("/api/dashboard/summary").json()
    assert summary["policy_count"] == 11

    process_response = client.delete("/api/processes/process_purchase")
    assert process_response.status_code == 200
    assert client.get("/api/processes/process_purchase").status_code == 404
    summary = client.get("/api/dashboard/summary").json()
    assert summary["process_count"] == 9


def test_export_findings_excel() -> None:
    client.post("/api/seed/reset")
    client.post(
        "/api/skill-runs",
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
            "process_ids": [],
            "knowledge_node_ids": [],
            "clarification_answers": {KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        },
    )

    response = client.get("/api/exports/findings.xlsx")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with zipfile.ZipFile(BytesIO(response.content)) as workbook:
        assert "xl/worksheets/sheet1.xml" in workbook.namelist()


def test_close_finding_sets_closed_time() -> None:
    client.post("/api/seed/reset")
    run_response = client.post(
        "/api/skill-runs",
        json={
            "skill_id": "skill_policy_conflict",
            "policy_ids": ["policy_purchase", "policy_sub_purchase"],
            "process_ids": [],
            "knowledge_node_ids": [],
            "clarification_answers": {KB_UNAVAILABLE_Q: "允许，本轮可先仅基于制度和流程证据生成结论。"},
        },
    )
    finding_id = run_response.json()["findings"][0]["id"]

    close_response = client.patch(f"/api/findings/{finding_id}", json={"status": "closed"})

    assert close_response.status_code == 200
    body = close_response.json()
    assert body["status"] == "closed"
    assert body["closed_at"]


def test_upload_policy_analyze_and_save_txt() -> None:
    client.post("/api/seed/reset")
    content = """测试采购制度
编号 TEST-001 版本 A/O 所属模块 采购
生效日期 2026/01/01
1 目的
为规范测试采购管理，制定本制度。
2 适用范围
适用于公司采购事项。
3 职责
采购中心负责采购策略和供应商管理。
4 流程
采购申请应由部门负责人审核。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("test-policy.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suitable"] is True
    assert len(body["clauses"]) >= 3

    save_response = client.post(
        f"/api/policy-uploads/{body['analysis_id']}/save",
        json={"category": "采购", "answers": {"code": "TEST-001"}},
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["category"] == "采购"
    assert saved["clauses"]


def test_upload_policy_parser_preserves_heading_levels() -> None:
    client.post("/api/seed/reset")
    content = """测试生产管理办法
编号 TEST-SC-001 版本 A/O 所属模块 生产
生效日期 2026/01/01
1 目的
为规范生产管理，制定本办法。
2 适用范围
适用于生产相关事项。
3 职责与分工
3.1 生产管理中心
3.1.1 负责生产计划管理。
(1) 负责汇总月度生产计划。
(2) 负责跟踪计划执行。
3.1.2 负责生产过程监督。
4 内容与要求
4.1 计划管理
4.1.1 月度计划应经审批后执行。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("test-level-policy.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    clauses = response.json()["clauses"]
    clause_nos = [clause["clause_no"] for clause in clauses]
    assert "3.1" in clause_nos
    assert "3.1.1" in clause_nos
    assert "3.1.1(1)" in clause_nos
    assert "4.1.1" in clause_nos
    child = next(clause for clause in clauses if clause["clause_no"] == "3.1.1(1)")
    parent = next(clause for clause in clauses if clause["clause_no"] == "3.1.1")
    assert child["parent_id"] == parent["id"]


def test_upload_policy_parser_supports_article_and_chinese_bullet_levels() -> None:
    client.post("/api/seed/reset")
    content = """电力公司非线性负荷用户接入管理办法
编号 DL-NL-001 版本 A/O 所属模块 接入管理
生效日期 2021/10/21
第一条 为规范非线性负荷用户接入管理，制定本办法。
第二条 适用范围
本办法适用于电力公司经营区域内非线性负荷用户接入。
（一） 用户应提交接入申请及负荷特性说明。
（二） 供电服务中心应组织电能质量评估。
第三条 技术要求
接入方案应满足电能质量控制要求，必要时可参见附件中的测试表格。
附件1：测试表格
1. 表格字段
附件内容暂不解析为制度条款。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("nonlinear-policy.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    clauses = response.json()["clauses"]
    clause_nos = [clause["clause_no"] for clause in clauses]
    assert "第一条" in clause_nos
    assert "第二条" in clause_nos
    assert "第二条(一)" in clause_nos
    assert "第二条(二)" in clause_nos
    assert "1" not in clause_nos
    child = next(clause for clause in clauses if clause["clause_no"] == "第二条(一)")
    parent = next(clause for clause in clauses if clause["clause_no"] == "第二条")
    assert child["parent_id"] == parent["id"]


def test_upload_policy_parser_supports_common_policy_heading_styles() -> None:
    client.post("/api/seed/reset")
    content = """综合制度标题识别办法
编号 MIX-001 版本 A/O 所属模块 综合
生效日期 2026/01/01
第一章 总则
第一条 制定目的
为提升制度解析质量，制定本办法。
第二条 适用范围
适用于多种标题样式的制度文件。
第一节 管理职责
第三条 职责划分
制度管理部门负责统一归口管理。
（一） 制度管理员负责源文件保留。
（二） 业务部门负责条款确认。
一、补充管理要求
涉及跨部门事项应形成复核记录。
二、附加说明
制度执行过程应保留证据。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("mixed-heading-policy.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    clauses = response.json()["clauses"]
    clause_nos = [clause["clause_no"] for clause in clauses]
    assert "第一章" in clause_nos
    assert "第一节" in clause_nos
    assert "第三条" in clause_nos
    assert "第三条(一)" in clause_nos
    assert "一" in clause_nos
    article = next(clause for clause in clauses if clause["clause_no"] == "第三条")
    bullet = next(clause for clause in clauses if clause["clause_no"] == "第三条(一)")
    assert bullet["parent_id"] == article["id"]


def test_upload_policy_parser_supports_markdown_heading_styles() -> None:
    client.post("/api/seed/reset")
    content = """Markdown制度指引
编号 MD-001 版本 A/O 所属模块 综合
生效日期 2026/01/01
# 总则
为规范 Markdown 制度文档管理，制定本指引。
## 适用范围
适用于 Markdown 形式维护的制度文件。
### 职责要求
制度管理员负责维护源文件。
1 目的
确保标题解析可以兼容 Markdown 与数字编号。
1.1 管理要求
应保留原始文件并支持下载。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("markdown-policy.md", content.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 200
    clauses = response.json()["clauses"]
    clause_nos = [clause["clause_no"] for clause in clauses]
    assert any(no.startswith("H1-") for no in clause_nos)
    assert any(no.startswith("H2-") for no in clause_nos)
    assert "1" in clause_nos
    assert "1.1" in clause_nos


def test_upload_policy_source_file_can_be_downloaded_before_and_after_save() -> None:
    client.post("/api/seed/reset")
    content = """测试源文件保留制度
编号 SRC-001 版本 A/O 所属模块 采购
生效日期 2026/01/01
第一条 为验证源文件保留，制定本制度。
第二条 适用范围
适用于源文件下载测试。
第三条 职责
采购中心负责保存制度源文件。
第四条 管理要求
制度管理员应在制度上传、解析、确认、保存和后续复核过程中保留源文件，确保制度原文可以被追溯、下载和复核。
第五条 附则
本制度由制度管理部门负责解释，自发布之日起执行。
"""
    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("source-policy.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_file"]["file_name"] == "source-policy.txt"

    source_response = client.get(f"/api/policy-uploads/{body['analysis_id']}/source")
    assert source_response.status_code == 200
    assert b"SRC-001" in source_response.content

    save_response = client.post(
        f"/api/policy-uploads/{body['analysis_id']}/save",
        json={"category": "采购", "answers": {"code": "SRC-001"}},
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["source_file"]["file_name"] == "source-policy.txt"
    policy_source_response = client.get(f"/api/policies/{saved['id']}/source")
    assert policy_source_response.status_code == 200
    assert policy_source_response.content == source_response.content


def test_seed_assets_have_initial_versions() -> None:
    client.post("/api/seed/reset")

    policy_versions = client.get("/api/policies/policy_purchase/versions")
    process_versions = client.get("/api/processes/process_purchase/versions")

    assert policy_versions.status_code == 200
    assert process_versions.status_code == 200
    assert len(policy_versions.json()) == 2
    assert policy_versions.json()[0]["status"] == "current"
    assert len(process_versions.json()) == 1
    assert process_versions.json()[0]["status"] == "current"


def test_upload_same_policy_code_creates_current_new_version() -> None:
    client.post("/api/seed/reset")
    existing = client.get("/api/policies/policy_purchase").json()
    initial_version_count = existing["version_count"]
    content = f"""{existing['name']}
编号 {existing['code']} 版本 B/O 所属模块 采购
生效日期 2026/06/01
第一条 制定目的
为更新饲料原料基差采购管理要求，制定本细则。
第二条 适用范围
适用于平台及下属单位饲料原料基差采购事项。
第三条 职责分工
采购中心负责采购申请、点价策略和供应商管理。
第四条 审批要求
单笔基差采购金额超过50万元的，应增加风控复核后提交平台总经理审批。
"""
    analyze_response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("purchase-v2.txt", content.encode("utf-8"), "text/plain")},
    )
    body = analyze_response.json()
    assert analyze_response.status_code == 200
    assert body["version_match"]["decision"] == "auto_version"
    assert body["version_match"]["policy_id"] == "policy_purchase"

    save_response = client.post(
        f"/api/policy-uploads/{body['analysis_id']}/save",
        json={"category": existing["category"], "answers": {}},
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["id"] == "policy_purchase"
    assert saved["version"] == "B/O"
    assert saved["version_count"] == initial_version_count + 1

    versions = client.get("/api/policies/policy_purchase/versions").json()
    assert len(versions) == initial_version_count + 1
    assert [item["status"] for item in versions].count("current") == 1
    assert versions[0]["version_no"] == "B/O"
    source_response = client.get(f"/api/policies/policy_purchase/versions/{versions[0]['id']}/source")
    assert source_response.status_code == 200
    assert b"B/O" in source_response.content


def test_low_confidence_version_match_requires_confirmation() -> None:
    client.post("/api/seed/reset")
    content = """饲料原料基差采购管理规范
编号  版本 A/O 所属模块 采购
生效日期 2026/06/01
第一条 制定目的
为规范饲料原料基差采购管理，制定本规范。
第二条 适用范围
适用于饲料采购相关事项。
第三条 职责分工
采购中心负责采购执行。
第四条 审批要求
重大采购事项应提交平台总经理审批。
"""
    analyze_response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("purchase-like.txt", content.encode("utf-8"), "text/plain")},
    )
    body = analyze_response.json()
    assert analyze_response.status_code == 200
    assert body["version_match"]["decision"] == "needs_confirmation"
    assert body["version_match"]["question"] in body["questions"]

    save_response = client.post(
        f"/api/policy-uploads/{body['analysis_id']}/save",
        json={"category": "采购", "answers": {}},
    )

    assert save_response.status_code == 400
    assert "置信度不足" in save_response.text


def test_upload_policy_soft_completeness_issues_do_not_block_admission(monkeypatch) -> None:
    monkeypatch.setenv("USE_REAL_LLM", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeDeepSeekClient:
        def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
            return {
                "suitable": False,
                "reasons": [
                    "缺失角色定义：正文中出现'平台公司业务分管领导''生产管理中心'等角色未明确定义。",
                    "缺失术语定义：如'饲料产品部''饲料厂'虽直接命名但未在制度中给出正式定义。",
                    "缺失违规追责条款：制度未设置监督检查和违规处理章节。",
                    "引用文件状态不明：正文引用多个工作指引，未说明版本/生效状态，需确认是否已发布。",
                ],
                "suggestions": [],
                "questions": [],
                "metadata": {
                    "name": "饲料生产管理细则",
                    "code": "YN-SC-9.1.1",
                    "version": "A/O",
                    "effective_date": "2026/01/01",
                    "category": "生产管理",
                    "org_scope": "公司及下属饲料厂",
                },
                "clauses": [
                    {"clause_no": "1", "title": "目的", "content": "为规范饲料生产管理，制定本细则。"},
                    {"clause_no": "2", "title": "适用范围", "content": "适用于公司饲料产品部及下属饲料厂。"},
                    {"clause_no": "3", "title": "职责", "content": "生产管理中心负责生产计划管理。"},
                    {"clause_no": "4", "title": "流程", "content": "重大生产事项报平台公司业务分管领导审批。"},
                ],
                "concepts": [
                    {"node_type": "Role", "name": "生产管理中心"},
                    {"node_type": "Document", "name": "点价申请单"},
                    {"node_type": "Matter", "name": "饲料生产管理"},
                ],
            }

    monkeypatch.setattr("app.policy_upload.DeepSeekClient", FakeDeepSeekClient)
    client.post("/api/seed/reset")
    content = """饲料生产管理细则
编号 YN-SC-9.1.1 版本 A/O 所属模块 生产管理
生效日期 2026/01/01
1 目的
为规范饲料生产管理，制定本细则。
2 适用范围
适用于公司饲料产品部及下属饲料厂。
3 职责
生产管理中心负责生产计划管理。
4 流程
重大生产事项报平台公司业务分管领导审批。
"""

    response = client.post(
        "/api/policy-uploads/analyze",
        files={"file": ("YN-SC-9.1.1.txt", content.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suitable"] is True
    assert body["reasons"] == []
    assert body["can_force_upload"] is True
    assert not any("后续再补充完善" in question for question in body["questions"])
    assert any("缺失角色定义" in suggestion for suggestion in body["suggestions"])
    assert body["concepts"] == [{"node_type": "人员角色", "name": "生产管理中心"}]
