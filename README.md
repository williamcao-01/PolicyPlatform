# AI 制度治理工作台 Demo

当前 demo 聚焦 3 个核验场景和 1 个入库场景：

1. 多制度冲突检查。
2. 制度与流程校验。
3. 无制度依据识别。
4. 上传制度文件：解析条款、判断是否适合入库、补充确认后保存到制度树，并更新 Knowledge Graph。

## 运行后端

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
$env:PYTHONPATH="C:\Users\willi\Documents\制度助手\backend"
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## 运行前端

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

## 测试

后端：

```powershell
$env:PYTHONPATH="C:\Users\willi\Documents\制度助手\backend"
.\.venv\Scripts\python -m pytest backend\tests -q
```

前端：

```powershell
cd frontend
npm test
npm run build
```

## Skills 架构

业务技能以文件形式定义在：

```text
backend/app/skills/
  policy_conflict/
    SKILL.md
    prompt.md
    schema.json
  policy_process_check/
    SKILL.md
    prompt.md
    schema.json
  no_policy_basis/
    SKILL.md
    prompt.md
    schema.json
  upload_policy_file/
    SKILL.md
    prompt.md
    schema.json
```

后端启动后通过 `SkillRegistry` 读取这些文件，`/api/skills` 返回 schema 中的技能定义，`/api/skill-runs` 使用对应 `prompt.md` 和 `SKILL.md` 组装模型输入。

Seed 数据只包含制度、BPMN、知识图谱等业务资产，不再内置答案结果。LLM 输出必须通过 evidence 白名单校验后才会写入 findings。

所有业务 Skill 执行前都会咨询专业知识库：

```text
KNOWLEDGE_BASE_ENABLED=true
KNOWLEDGE_API_URL=http://127.0.0.1:8765
```

知识库用于专业判断框架、术语边界、治理建议和不确定性识别。风险 finding 的正式证据仍只能来自制度条款或 BPMN 节点；知识库引用会作为 `professional_references` 返回。如果知识库不可用，Skill 会继续运行，但会生成需要用户确认的问题，并写入 hook。

上传制度文件 Skill 使用同一套文件化定义，但运行入口是上传专用接口：

```text
POST /api/policy-uploads/analyze
POST /api/policy-uploads/{analysis_id}/save
```

上传分析阶段只做解析、合理性判断、条款拆分、问题生成和术语抽取，不直接入库。用户选择制度树结构项并补充必要问题后，保存接口才会写入制度树和 Knowledge Graph。

## 大模型配置

当前 demo 默认使用本地规则 skill runner。需要测试 DeepSeek v4 flash 生成质量时，设置：

不要把 API key 写入代码或文档。需要真实调用时，在本地环境设置：

```powershell
$env:DEEPSEEK_API_KEY="..."
$env:DEEPSEEK_BASE_URL="https://api.deepseek.com"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
$env:USE_REAL_LLM="true"
```

质量评测：

```powershell
$env:PYTHONPATH="C:\Users\willi\Documents\制度助手\backend"
$env:USE_REAL_LLM="true"
.\.venv\Scripts\python -m app.quality_eval
```

评测结果会写入 `backend/quality-eval-result.json`，该文件不会入库。

DeepSeek 模型确认使用 `deepseek-v4-flash`，记录在 [docs/decision-log.md](C:/Users/willi/Documents/制度助手/docs/decision-log.md)。
