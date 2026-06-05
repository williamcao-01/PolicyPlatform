# 三列 AI 制度工作台 Demo 架构与开发计划 v0.1

## 1. 结论

当前 `mvp-technical-plan-v0.1` 的底层架构可以支撑三列 Chat 工作台，但需要补充三类能力：

1. 前端从传统多页面后台调整为单页工作台：
   - 顶部指标区
   - 左侧资产树
   - 中间 Chat 交互区
   - 右侧 Skill 启动区
   - 详情内容用抽屉、弹窗或中间结果卡片承载

2. 审批流从普通流程节点数据升级为 BPMN 文件资产：
   - 每个流程样例必须有 `.bpmn` 原始文件
   - 后端保存 BPMN XML
   - 前端用 BPMN viewer 渲染
   - 结构化节点仍落库，用于制度-流程校验

3. 增加 Chat/Skill 编排对象：
   - ChatSession
   - ChatMessage
   - SkillDefinition
   - SkillRun
   - SkillInputRequest
   - GeneratedArtifact

因此不是推翻原架构，而是在原来的 Domain/Harness/Skill 层上增加一个 AI Workbench 层。

## 2. 目标界面

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 顶部指标：制度数 / BPMN 流程数 / 术语数 / 风险数 / 待复核数 / 已关闭问题数 │
├───────────────────────┬────────────────────────────────┬──────────────────┤
│ 左侧资产上下文          │ 中间 Chat 工作区                │ 右侧 Skill 面板   │
│                       │                                │                  │
│ 1. 制度树              │ 对话消息                         │ 多制度冲突检查     │
│    - 采购管理办法       │ Skill 输入提示                    │ 制度与流程校验     │
│    - 合同管理办法       │ 运行过程                         │ 无制度依据识别     │
│                       │ 结果卡片                         │                  │
│ 2. BPMN 流程树         │ 证据引用                         │                  │
│    - 采购申请流程       │ 生成物预览                       │                  │
│    - 合同审批流程       │                                │ 整改建议生成       │
│                       │                                │                  │
│ 3. Knowledge Graph     │                                │                  │
│    - 事项              │                                │                  │
│    - 角色              │                                │                  │
│    - 动作              │                                │                  │
└───────────────────────┴────────────────────────────────┴──────────────────┘
```

## 3. 左侧资产树设计

### 3.1 制度树

用途：

- 展示系统当前收录制度。
- 支持按组织、制度类型、状态分组。
- 点击制度后，中间 Chat 可自动引用当前制度上下文。
- 可展开到章节条款。

树结构：

```text
制度文件
  采购
    采购管理办法 v2024
      第一章 总则
      第二章 采购权限
      第三章 审批流程
  合同
    合同管理办法 v2024
```

前端组件：

- Ant Design Tree
- 搜索框
- 状态标签
- 右键或更多菜单：查看详情、引用到对话、发起检查

### 3.2 BPMN 流程树

用途：

- 展示结构化审批流资产。
- 每个样例流程必须对应一个 BPMN 文件。
- 点击流程后可打开 BPMN 预览。
- Chat 可引用某个流程作为 Skill 输入。

树结构：

```text
审批流程
  采购
    采购申请流程.bpmn
    采购合同审批流程.bpmn
  人力
    招聘录用流程.bpmn
    薪酬定级流程.bpmn
```

前端组件：

- Ant Design Tree
- `bpmn-js` 或 `bpmn-js-viewer`
- 流程详情抽屉：BPMN 图、节点列表、关联制度、已发现问题

技术调整：

- 保留 `ProcessDefinition` 和 `ProcessNode`。
- 新增 `ProcessAsset` 存储 BPMN XML 和文件元数据。
- Seed 数据中生成真实 `.bpmn` 文件，而不是只生成 JSON 节点。

### 3.3 Knowledge Graph

用途：

- 展示制度和流程中抽象出的企业词汇。
- 第一版重点展示，不作为核心判断依据。
- 可点击术语，将术语加入 Chat 上下文。

节点类型：

| 类型 | 示例 |
|---|---|
| Matter | 采购申请、合同签订、费用报销 |
| Role | 经办人、部门负责人、法务、总经理 |
| Action | 审核、审批、备案、会签 |
| Condition | 金额超过 30 万、涉及重大合同 |
| Organization | 平台公司、子公司、事业部 |
| Document | 采购管理办法、合同管理办法 |
| Process | 采购申请流程、合同审批流程 |

边类型：

| 边 | 含义 |
|---|---|
| defined_in | 术语定义于某制度条款 |
| used_by | 术语被某审批流使用 |
| approves | 某角色审批某事项 |
| requires | 某事项要求某动作 |
| conflicts_with | 两个规则存在冲突 |
| maps_to | 流程节点映射到制度条款 |

前端组件：

- Demo 第一版可用简化树或列表表达。
- 如果要图形化，建议用 Cytoscape.js。
- 不建议第一版引入 Neo4j；图谱数据仍用 PostgreSQL 表存储。

## 4. 中间 Chat 工作区设计

中间区域不是普通聊天框，而是任务型 Chat：

```text
用户自然语言
→ 选择或点选 Skill
→ Skill 提示所需输入
→ 用户从左侧资产树选择制度/流程/术语
→ Harness 组装上下文
→ Skill 运行
→ Chat 返回结构化结果卡片
→ 用户确认生成物或更新左侧资产
```

### 4.1 Chat 消息类型

| 类型 | 说明 |
|---|---|
| user_text | 用户输入 |
| assistant_text | 普通回答 |
| skill_prompt | Skill 要求补充输入 |
| skill_running | Skill 运行状态 |
| skill_result | Skill 结果 |
| evidence_card | 证据引用卡片 |
| finding_card | 风险问题卡片 |
| artifact_card | 生成物卡片 |
| asset_update | 资产更新提示 |

### 4.2 Skill 交互协议

右侧点击 Skill 后，中间 Chat 不直接执行，而是先创建输入收集过程：

```text
用户点击“制度与流程校验”
→ Chat 提示：请选择 1 份制度和 1 条 BPMN 流程
→ 用户从左侧制度树选择《采购管理办法》
→ 用户从左侧流程树选择“采购申请流程.bpmn”
→ Chat 展示待执行摘要
→ 用户确认执行
→ Harness 运行 skill
→ 返回问题、证据、建议
```

### 4.3 生成物类型

| 生成物 | 示例 |
|---|---|
| Finding | 风险问题 |
| Evidence | 证据引用 |
| SuggestedClause | 制度修订条款草案 |
| ProcessMapping | 流程节点与制度条款映射 |
| BPMNAnnotation | 对 BPMN 节点增加风险标注 |
| AuthorityRuleDraft | 候选权责规则 |
| ReportDraft | 检查报告草稿 |

## 5. 右侧 Skill 面板

MVP 先只放 3 个 Demo Skill：

| Skill | 输入 | 输出 |
|---|---|---|
| 多制度冲突检查 | 2-N 份制度 | 冲突矩阵、证据引用、风险等级 |
| 制度与流程校验 | 1 份制度 + 1 条 BPMN 流程 | 缺失节点、多余节点、权限错配 |
| 无制度依据识别 | 1 条 BPMN 流程 + 可选制度范围 | 疑似无依据节点、建议处理方式 |

右侧 Skill 卡片字段：

```text
名称
一句话说明
所需输入
输出类型
是否需要人工确认
是否可更新资产
```

## 6. 顶部指标区

MVP 指标：

| 指标 | 口径 |
|---|---|
| 收录制度 | PolicyDocument 总数 |
| BPMN 流程 | ProcessAsset 总数 |
| 企业术语 | KnowledgeNode 总数 |
| 已识别风险 | Finding 总数 |
| 待人工复核 | Finding status = pending_review |
| 已完成整改 | Finding status = closed |

第一版顶部指标只做当前 seed dataset 的统计，不做复杂趋势分析。

## 7. 需要补充的数据模型

### 7.1 Chat 对象

| 对象 | 字段 |
|---|---|
| ChatSession | id, title, created_by, created_at, updated_at, active_context |
| ChatMessage | id, session_id, role, message_type, content, attachments, created_at |
| ChatContextItem | id, session_id, item_type, item_id, label, pinned |

### 7.2 Skill 对象

| 对象 | 字段 |
|---|---|
| SkillDefinition | id, name, description, input_schema, output_schema, enabled |
| SkillRun | id, session_id, skill_id, task_id, status, input_payload, output_payload, started_at, finished_at |
| SkillInputRequest | id, skill_run_id, field_name, field_type, required, resolved_value |

### 7.3 BPMN 对象

| 对象 | 字段 |
|---|---|
| ProcessAsset | id, process_definition_id, file_name, file_path, bpmn_xml, checksum, created_at |
| BpmnElement | id, process_asset_id, element_id, element_type, name, role, order_index |
| BpmnAnnotation | id, process_asset_id, element_id, annotation_type, finding_id, content |

### 7.4 Knowledge Graph 对象

| 对象 | 字段 |
|---|---|
| KnowledgeNode | id, node_type, name, normalized_name, description, source_count |
| KnowledgeEdge | id, source_node_id, target_node_id, edge_type, evidence_id, confidence |

## 8. 技术栈调整

| 位置 | 原建议 | 调整 |
|---|---|---|
| 流程图展示 | React Flow | BPMN 文件用 `bpmn-js-viewer`，自定义流程关系可继续用 React Flow |
| 知识图谱展示 | 未明确 | 第一版树/列表，增强版 Cytoscape.js |
| 页面形态 | 多页面后台 | 单页三列 Workbench + 抽屉详情 |
| Skill 操作 | 任务中心发起 | Chat + 右侧 Skill 面板发起 |
| 流程数据 | JSON 节点 | BPMN XML + 结构化节点双存储 |

## 9. 串行开发主线

这些任务有明确依赖，建议串行推进：

1. 确定前后端项目骨架。
2. 定义 demo seed 数据格式。
3. 实现后端核心 schema。
4. 实现 seed：制度、BPMN、知识图谱、Skill、Finding。
5. 实现 API contract。
6. 实现三列工作台静态布局。
7. 接入真实 API 数据。
8. 实现 Chat + Skill 输入收集。
9. 实现 mock SkillRun。
10. 实现结果卡片与资产更新提示。
11. 联调完整 demo 流程。
12. 浏览器验收和交互修正。

## 10. 并行开发计划

### 阶段 0：接口冻结

负责人建议：架构/后端 lead。

产出：

- OpenAPI 草案
- seed 数据 JSON schema
- BPMN 文件目录规范
- 3 个 Demo SkillDefinition 清单
- 前端 mock 数据结构

必须先完成，否则多 agent 会互相阻塞。

### 阶段 1：并行基础建设

| Agent | 任务 | 产出 |
|---|---|---|
| Backend Agent | FastAPI、数据库模型、seed API | `/api/dashboard`, `/api/policies`, `/api/processes`, `/api/skills` |
| Seed Agent | 生成制度文本、BPMN XML、知识图谱、golden findings | `demo_dataset` |
| Frontend Shell Agent | 三列布局、顶部指标、全局状态 | Workbench UI |
| UI Component Agent | 制度树、流程树、Skill 卡片、Chat 消息组件 | 可复用组件 |

并行条件：

- 使用同一份 mock schema。
- 前端先读本地 mock，后端完成后切 API。

### 阶段 2：并行功能接入

| Agent | 任务 | 产出 |
|---|---|---|
| Policy Agent | 制度树、制度详情抽屉、条款引用 | 制度上下文选择 |
| BPMN Agent | BPMN viewer、流程树、节点详情 | 流程上下文选择 |
| KG Agent | 术语树/图谱、术语引用 | Knowledge Graph 面板 |
| Chat Agent | ChatSession、消息流、上下文 pinning | 中间对话区 |
| Skill Agent | Skill 输入收集、SkillRun 状态、结果卡片 | 可点选执行 skill |

### 阶段 3：串行联调

联调顺序：

1. 进入工作台，顶部指标正常。
2. 左侧制度树、流程树、图谱数据正常。
3. 点击 Skill 后，Chat 提示输入。
4. 从左侧选择制度和 BPMN 流程。
5. Chat 显示执行摘要。
6. 执行 mock SkillRun。
7. 返回 Finding 卡片、Evidence 卡片、Suggestion 卡片。
8. 风险数和待复核数更新。
9. 点击结果可定位到制度条款或 BPMN 节点。

### 阶段 4：验收与修正

验收场景：

1. 多制度冲突检查：选择《采购管理办法》和《子公司采购实施细则》，输出金额阈值或审批主体冲突。
2. 制度与流程校验：选择《采购管理办法》和“采购申请流程.bpmn”，输出缺失节点、多余节点或权限错配。
3. 无制度依据识别：选择“招聘录用流程.bpmn”，输出“定薪审批节点”疑似缺少制度依据。

## 11. Demo 开发任务拆分

### Backend Agent Backlog

1. 创建 FastAPI 项目。
2. 定义 SQLAlchemy models。
3. 实现 seed reset/load。
4. 实现 dashboard summary API。
5. 实现 policies tree API。
6. 实现 processes tree API。
7. 实现 knowledge graph API。
8. 实现 skills list API。
9. 实现 chat session/message API。
10. 实现 mock skill run API。

### Seed Agent Backlog

1. 生成 8 份制度 Markdown 或 JSON 条款。
2. 生成 3-4 个 BPMN XML 文件，其中必须包含采购申请流程和招聘录用流程。
3. 生成 30-60 个知识图谱节点。
4. 生成 50-100 条图谱边。
5. 生成 8-12 条 golden findings，全部服务于 3 个 demo 场景。
6. 生成 3 个 SkillDefinition。

### Frontend Shell Agent Backlog

1. Vite + React + TypeScript + Ant Design。
2. AppShell：顶部指标 + 三列布局。
3. 左侧折叠分区。
4. 中间 Chat 面板。
5. 右侧 Skill 面板。
6. 全局 selected context store。

### Asset UI Agent Backlog

1. PolicyTree。
2. ProcessTree。
3. BpmnViewerDrawer。
4. KnowledgeGraphPanel。
5. EvidenceLocator。

### Chat/Skill Agent Backlog

1. ChatMessageList。
2. ChatComposer。
3. SkillCard。
4. SkillInputCollector。
5. SkillRunTimeline。
6. FindingResultCard。
7. ArtifactCard。

## 12. 风险与约束

1. BPMN viewer 和 React Flow 不要混用同一个流程展示场景。MVP 中审批流文件展示用 BPMN viewer。
2. Knowledge Graph 第一版不要承担判断职责，只承担上下文浏览和引用。
3. Chat 不应替代结构化输入。Skill 所需输入必须由 schema 驱动。
4. Skill 输出必须落成结构化卡片，不能只返回一段自然语言。
5. 所有 Finding 必须能定位到制度条款或 BPMN 节点。
6. Demo 阶段可以 mock AI，但数据结构要按真实 Harness 设计。

## 13. 是否支撑的最终判断

支撑。

但实现路径应从“页面清单型后台”调整成“资产上下文 + Chat + Skill orchestration”的工作台架构。原来的制度、流程、检查任务、问题、证据、Harness、Skill 设计仍然有效；新增 Chat、BPMN Asset、Knowledge Graph、SkillRun 四组对象后，可以支撑你描述的 demo 形态。
