# AI 制度管理模块 MVP 技术方案 v0.1

## 1. MVP 定位

本 MVP 的目标不是一次性完成完整的制度治理平台，而是先跑通一个可信、可演示、可评测的闭环：

```text
测试制度/审批流初始化
→ 制度文档结构化
→ 审批流结构化
→ 创建检查任务
→ 执行规则检查与 AI 辅助检查
→ 生成问题清单
→ 绑定证据引用
→ 生成整改建议
→ 人工确认/关闭问题
```

第一版不直接接入真实 OA/K2，不做全量自动扫描，不把 AI 抽取结果直接作为正式制度依据。系统先内置一批制度文档、审批流和标准问题，用于产品演示、开发调试和后续 A/B 评测。

## 2. 技术选型

| 层级 | 推荐选型 | 说明 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 轻量、启动快，适合 MVP |
| UI 组件 | Ant Design | 企业后台成熟，表格、表单、抽屉、步骤条够用 |
| 数据表格 | TanStack Table 或 Ant Design Table | MVP 可先用 Ant Design Table |
| 流程图 | React Flow | 展示审批节点、条件分支和匹配结果 |
| 后端 | FastAPI | Python 生态适合文档解析、AI workflow 和评测 |
| 数据库 | PostgreSQL | 结构化数据主库 |
| 向量检索 | pgvector | 先避免引入独立向量数据库 |
| ORM | SQLAlchemy + Alembic | 明确迁移和模型管理 |
| 异步任务 | FastAPI BackgroundTasks 起步，后续 Celery + Redis | MVP 先降低部署复杂度 |
| 文档解析 | python-docx + PyMuPDF | 支持 DOCX/PDF，MVP 可先重点支持 DOCX/Markdown |
| 文件存储 | 本地文件目录，封装 Storage 接口 | 后续可替换对象存储 |
| AI Provider | Provider Adapter | 避免业务逻辑绑定具体模型 |
| 评测 | pytest + golden dataset | 对比问题命中率、误报率、证据准确率 |

暂不建议第一版引入 Neo4j。Ontology 关系可以先用 PostgreSQL 表和 JSONB 表达，等后续出现复杂多跳影响分析需求后再评估图数据库。

## 3. 分层架构

```text
Frontend
  工作台首页
  制度文档中心
  审批流中心
  检查任务中心
  检查结果详情
  问题闭环中心
  测试数据管理

API Layer
  policy API
  clause API
  process API
  check task API
  finding API
  rule API
  seed dataset API

Domain Layer
  PolicyDocument
  PolicyClause
  AuthorityRule
  ProcessDefinition
  ProcessNode
  CheckTask
  Finding
  EvidenceSpan

Harness Layer
  ContextBuilder
  SkillRunner
  OutputParser
  EvidenceVerifier
  EvaluationLogger

Skill Layer
  structure_policy_doc
  format_check
  compare_policies
  extract_authority_rules
  map_process_to_policy
  detect_unbacked_flow_node
  generate_remediation_suggestion
  evidence_verify

Knowledge Layer
  policy text index
  process index
  term dictionary
  optional wiki knowledge base

Storage
  PostgreSQL
  pgvector
  local file storage
```

## 4. Ontology 初版

### 4.1 制度侧对象

| 对象 | 含义 | 关键字段 |
|---|---|---|
| PolicyDocument | 制度文件 | name, code, version, issuer, effective_date, status, org_scope, category |
| PolicyClause | 制度条款 | document_id, clause_no, title, content, parent_clause_id, order_index |
| PolicyMatter | 制度事项 | name, normalized_name, category, description |
| AuthorityRule | 权责规则 | matter_id, subject_role, action, object_scope, org_scope, condition, source_clause_id, confidence, review_status |
| EvidenceSpan | 证据片段 | source_type, source_id, document_id, clause_id, quote, page_no, char_start, char_end |

### 4.2 流程侧对象

| 对象 | 含义 | 关键字段 |
|---|---|---|
| ProcessDefinition | 审批流 | name, code, business_domain, org_scope, status, source_system |
| ProcessNode | 流程节点 | process_id, node_name, node_type, role, action, condition, order_index |
| ProcessEdge | 节点关系 | process_id, from_node_id, to_node_id, condition |
| ProcessPolicyMapping | 流程-制度映射 | process_id, node_id, policy_document_id, clause_id, authority_rule_id, match_score, review_status |

### 4.3 检查侧对象

| 对象 | 含义 | 关键字段 |
|---|---|---|
| CheckTask | 检查任务 | name, task_type, check_type, target_scope, status, created_by, started_at, finished_at |
| CheckRun | 单次执行记录 | task_id, skill_name, input_snapshot, output_snapshot, model_name, cost, duration_ms |
| Finding | 问题项 | task_id, finding_type, title, description, severity, status, confidence, owner_department |
| FindingEvidence | 问题证据 | finding_id, evidence_span_id, evidence_role |
| RemediationSuggestion | 整改建议 | finding_id, suggestion_text, suggested_clause_text, generated_by, review_status |

## 5. 页面清单

| 页面 | MVP 功能 | 主要组件 |
|---|---|---|
| 工作台首页 | 展示模块总览和快捷入口 | 指标卡、最近任务、风险分布、快捷按钮 |
| 制度文档中心 | 查看和管理制度 | 列表、筛选、上传、状态标签 |
| 制度详情页 | 查看制度结构化结果 | 元信息、条款树、原文区、关联问题 |
| 审批流中心 | 查看测试审批流 | 流程列表、业务域筛选、关联制度数量 |
| 审批流详情页 | 查看流程节点和制度匹配 | React Flow、节点列表、匹配证据面板 |
| 创建检查任务 | 发起单次检查 | 对象选择、检查类型、规则模板、确认页 |
| 检查任务中心 | 查看任务执行状态 | 任务表、状态筛选、失败重试 |
| 检查结果详情 | 查看问题和证据 | 问题分组、风险等级、证据引用、建议 |
| 问题闭环中心 | 跟踪整改 | 问题表、状态流转、责任部门、复核记录 |
| 规则配置页 | 配置轻量规则 | 格式规则、流程规则、风险等级规则 |
| 测试数据管理 | 生成/重置演示数据 | 数据集列表、初始化按钮、重置按钮 |

## 6. 页面/API 对照表

| 页面 | API |
|---|---|
| 工作台首页 | GET /api/dashboard/summary, GET /api/check-tasks/recent, GET /api/findings/stats |
| 制度文档中心 | GET /api/policies, POST /api/policies/upload, POST /api/policies/{id}/parse |
| 制度详情页 | GET /api/policies/{id}, GET /api/policies/{id}/clauses, GET /api/policies/{id}/findings |
| 审批流中心 | GET /api/processes |
| 审批流详情页 | GET /api/processes/{id}, GET /api/processes/{id}/nodes, GET /api/processes/{id}/mappings |
| 创建检查任务 | POST /api/check-tasks, GET /api/check-templates |
| 检查任务中心 | GET /api/check-tasks, POST /api/check-tasks/{id}/run |
| 检查结果详情 | GET /api/check-tasks/{id}/results, GET /api/findings/{id} |
| 问题闭环中心 | GET /api/findings, PATCH /api/findings/{id}, POST /api/findings/{id}/comments |
| 规则配置页 | GET /api/rules, POST /api/rules, PATCH /api/rules/{id} |
| 测试数据管理 | POST /api/seed/reset, POST /api/seed/load-demo, GET /api/seed/status |

## 7. Harness/Skill 协议

### 7.1 Harness 职责

Harness 不直接做业务判断，而是负责把一次检查变成可控执行过程：

```text
读取检查任务
→ 加载目标制度/流程/规则
→ 构造 skill 输入
→ 调用 skill
→ 校验输出 schema
→ 校验证据引用
→ 写入 Finding/CheckRun
→ 标记待人工复核
```

### 7.2 Skill 输入格式

```json
{
  "task_id": "task_001",
  "skill_name": "compare_policies",
  "targets": {
    "policy_document_ids": ["policy_purchase", "policy_contract"],
    "process_ids": []
  },
  "context": {
    "clauses": [],
    "authority_rules": [],
    "process_nodes": [],
    "rules": [],
    "knowledge_context": []
  },
  "options": {
    "require_evidence": true,
    "allow_knowledge_base": false,
    "output_language": "zh-CN"
  }
}
```

### 7.3 Skill 输出格式

```json
{
  "skill_name": "compare_policies",
  "task_id": "task_001",
  "findings": [
    {
      "finding_type": "policy_conflict",
      "title": "采购金额阈值存在冲突",
      "description": "两份制度对小额采购审批阈值规定不一致。",
      "severity": "medium",
      "confidence": 0.78,
      "evidence": [
        {
          "source_type": "policy_clause",
          "document_id": "policy_purchase",
          "clause_id": "clause_3_2",
          "quote": "单笔采购金额超过 30 万元的，应提交平台总经理审批。"
        }
      ],
      "suggestion": "建议统一采购金额阈值，并明确平台与子公司的适用边界。"
    }
  ],
  "warnings": []
}
```

### 7.4 证据约束

核心判断链必须遵守：

```text
没有 evidence，不落 Finding
引用不来自制度/流程原文，不作为制度依据
knowledge base 只能用于解释和建议，不能单独支撑问题结论
AI 生成的权责规则默认 review_status = pending
```

## 8. Knowledge Base 接入策略

第一版保留接口，但默认关闭。

```text
核心结论链：
制度原文 + 流程文件 + 人工确认规则

辅助建议链：
制度原文 + 流程文件 + 人工确认规则 + 可选 knowledge base
```

后续用 A/B 测试判断是否启用：

| 组别 | 输入 |
|---|---|
| A | 原文 + 规则 |
| B | 原文 + Ontology |
| C | 原文 + Ontology + Harness |
| D | 原文 + Ontology + Harness + Knowledge Base |

评测指标：

| 指标 | 说明 |
|---|---|
| 问题命中率 | 预置问题是否被识别 |
| 误报率 | 是否误判正常制度/流程 |
| 证据准确率 | 引用是否真的支持结论 |
| 建议可采纳性 | 建议是否能给业务人员使用 |
| 输出稳定性 | 多次运行是否一致 |
| 成本与耗时 | 是否值得引入复杂链路 |

## 9. 测试数据设计

### 9.1 内置制度文件

| 制度 | 用途 |
|---|---|
| 采购管理办法 | 采购金额阈值、审批主体、流程一致性 |
| 合同管理办法 | 合同会签、法务审核、授权冲突 |
| 费用报销管理办法 | 小额事项、审批链过长 |
| 招聘录用管理办法 | 录用流程、岗位审批 |
| 薪酬定级管理指引 | 招聘后定薪衔接 |
| 子公司制度管理细则 | 子公司承接集团制度 |
| 印章使用管理办法 | 印章审批主体与使用范围 |
| 制度编写规范 | 格式检查规则 |

### 9.2 内置审批流

| 审批流 | 关联制度 | 预置问题 |
|---|---|---|
| 采购申请流程 | 采购管理办法 | 小额采购审批链过长、阈值不一致 |
| 招聘录用流程 | 招聘录用管理办法、薪酬定级管理指引 | 定薪环节制度依据不足 |
| 子公司采购审批流程 | 子公司制度管理细则、采购管理办法 | 子公司流程与平台采购权限要求不一致 |

### 9.3 Golden Findings

第一版准备 8-12 条标准问题，集中服务 3 个 demo 场景：

| 类型 | 示例 |
|---|---|
| policy_conflict | 两份制度对同一采购阈值规定不一致 |
| authority_mismatch | 采购流程审批主体与制度规定不一致 |
| missing_process_node | 采购申请流程缺少制度要求的风控复核节点 |
| extra_process_node | 采购申请流程存在制度未要求的多余高层审批节点 |
| no_policy_basis | 定薪节点未找到明确制度依据 |

每条 golden finding 必须包含：

```text
问题类型
风险等级
应命中的制度/流程
应引用的条款或节点
期望说明
期望建议方向
```

## 10. 第一阶段开发任务

### 10.1 后端

1. 建立 FastAPI 项目结构。
2. 建立 PostgreSQL schema 和 Alembic migration。
3. 实现 seed demo dataset。
4. 实现制度、条款、审批流、节点的基础 CRUD。
5. 实现检查任务创建和执行状态流转。
6. 实现 Finding 写入、查询、状态更新。
7. 实现 3 个 demo skill 的 mock runner：多制度冲突、制度与流程校验、无制度依据识别。
8. 实现 mock AI skill runner，先用预置 golden finding 生成结果。

### 10.2 前端

1. 建立 React + TypeScript + Ant Design 项目。
2. 实现应用框架、导航和工作台首页。
3. 实现制度文档中心和制度详情页。
4. 实现审批流中心和审批流详情页。
5. 实现创建检查任务页面。
6. 实现检查结果详情页。
7. 实现问题闭环中心。
8. 实现测试数据管理页。

### 10.3 验收标准

1. 一键生成测试制度、审批流和预置问题。
2. 用户能查看制度条款树和审批流节点图。
3. 用户能创建检查任务并得到问题清单。
4. 每条问题都有证据引用和整改建议。
5. 用户能将问题标记为待处理、处理中、已关闭、已退回。
6. 系统能区分制度依据、流程依据和 knowledge base 辅助信息。

## 11. 后续阶段

第二阶段：接入 3 个真实 AI skill，替换 mock skill runner。

第三阶段：实现候选权责抽取和人工确认工作台。

第四阶段：实现流程一致性检查和无制度依据节点识别。

第五阶段：做 knowledge base A/B 评测，决定是否进入默认链路。

第六阶段：扩展批量检查、异步任务和报告导出。
