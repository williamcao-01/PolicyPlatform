import { Alert, Button, Card, Input, Space } from 'antd';
import { Bot, Send, UserRound } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { ProfessionalReference, SkillDefinition, SkillRunResult, WorkbenchContext } from '../types';
import { downloadFindingsWorkbook } from '../xlsxExport';

type Props = {
  skills: SkillDefinition[];
  context: WorkbenchContext;
  assetLabelMap: Record<string, string>;
  results: SkillRunResult[];
  runningSkillId: string | null;
  error: string | null;
  onSkillRun: (skillId: string, clarificationAnswers?: Record<string, string>) => Promise<void>;
  onExportFindingsExcel: () => Promise<void>;
};

type ChatEvent =
  | { id: string; type: 'message'; role: 'user' | 'assistant'; content: string }
  | { id: string; type: 'result'; result: SkillRunResult };

export function ChatWorkbench({ skills, context, assetLabelMap, results, runningSkillId, error, onSkillRun, onExportFindingsExcel }: Props) {
  const [draft, setDraft] = useState('');
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [renderedResultIds, setRenderedResultIds] = useState<string[]>([]);
  const [answeredQuestionResultId, setAnsweredQuestionResultId] = useState<string | null>(null);
  const suppressNextRunAnnouncement = useRef(false);
  const previousRunningSkillId = useRef<string | null>(null);
  const latestResult = results.at(-1);
  const pendingQuestions = latestResult && latestResult.id !== answeredQuestionResultId ? latestResult.questions : [];

  useEffect(() => {
    const newResults = results.filter((result) => !renderedResultIds.includes(result.id));
    if (!newResults.length) return;
    setEvents((items) => [...items, ...newResults.map((result) => ({ id: result.id, type: 'result' as const, result }))]);
    setRenderedResultIds((items) => [...items, ...newResults.map((result) => result.id)]);
  }, [renderedResultIds, results]);

  useEffect(() => {
    const previous = previousRunningSkillId.current;
    if (runningSkillId && runningSkillId !== previous) {
      if (suppressNextRunAnnouncement.current) {
        suppressNextRunAnnouncement.current = false;
      } else {
        const skill = skills.find((item) => item.id === runningSkillId);
        setEvents((items) => [
          ...items,
          {
            id: `user_task_${Date.now()}`,
            type: 'message',
            role: 'user',
            content: taskRequestText(skill, context, assetLabelMap)
          }
        ]);
      }
    }
    previousRunningSkillId.current = runningSkillId;
  }, [assetLabelMap, context, runningSkillId, skills]);

  async function submitNaturalLanguage() {
    const text = draft.trim();
    if (!text) return;
    setEvents((items) => [...items, { id: `user_${Date.now()}`, type: 'message', role: 'user', content: text }]);
    setDraft('');

    if (isExcelExportRequest(text)) {
      try {
        const currentFindings = results.flatMap((result) => result.findings);
        if (currentFindings.length) {
          downloadFindingsWorkbook(currentFindings, `对话输出结果-${new Date().toISOString().slice(0, 10)}.xlsx`);
        } else {
          await onExportFindingsExcel();
        }
        setEvents((items) => [
          ...items,
          {
            id: `assistant_${Date.now()}`,
            type: 'message',
            role: 'assistant',
            content: currentFindings.length
              ? '已将当前对话中的输出结果整理为 Excel，并开始下载。'
              : '当前对话没有可导出的结果，已改为下载全部待解决风险清单。'
          }
        ]);
      } catch {
        setEvents((items) => [...items, unsupportedMessage()]);
      }
      return;
    }

    if (latestResult && pendingQuestions.length > 0 && !looksLikeNewTask(text)) {
      const answers = Object.fromEntries(pendingQuestions.map((question) => [question.question, text]));
      setAnsweredQuestionResultId(latestResult.id);
      suppressNextRunAnnouncement.current = true;
      setEvents((items) => [
        ...items,
        {
          id: `assistant_${Date.now()}`,
          type: 'message',
          role: 'assistant',
          content: `已收到。下面我会把你的回复作为确认信息，继续执行“${skillName(latestResult.skill_id, skills)}”。`
        }
      ]);
      await onSkillRun(latestResult.skill_id, answers);
      return;
    }

    const matchedSkill = explicitSkillRequest(text, skills);

    if (matchedSkill) {
      suppressNextRunAnnouncement.current = true;
      await onSkillRun(matchedSkill.id);
      return;
    }

    setEvents((items) => [...items, unsupportedMessage()]);
  }

  return (
    <main className="chat-workbench">
      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Space direction="vertical" size={12} className="results-stack">
        {events.map((event) =>
          event.type === 'message' ? (
            <div className={event.role === 'user' ? 'chat-row user' : 'chat-row assistant'} key={event.id}>
              <div className="chat-avatar">{event.role === 'user' ? <UserRound size={16} /> : <Bot size={16} />}</div>
              <div className="chat-message compact">{event.content}</div>
            </div>
          ) : (
            <SkillResultCard result={event.result} key={event.id} />
          )
        )}
        {runningSkillId ? <RunningSkillStrip skillName={skillName(runningSkillId, skills)} /> : null}
      </Space>

      {pendingQuestions.length ? (
        <div className="pending-chat-strip">
          <strong>等待确认</strong>
          <span>请在下方输入框回复，系统会带着你的回答继续执行当前任务。</span>
        </div>
      ) : null}

      <div className="composer">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={pendingQuestions.length ? '回复待确认项，系统会继续执行当前任务' : '输入补充说明，或从右侧点选任务'}
          onPressEnter={() => void submitNaturalLanguage()}
        />
        <Button icon={<Send size={16} />} type="primary" onClick={() => void submitNaturalLanguage()}>
          发送
        </Button>
      </div>
    </main>
  );
}

function unsupportedMessage(): ChatEvent {
  return {
    id: `assistant_${Date.now()}`,
    type: 'message',
    role: 'assistant',
    content: '我无法为你完成这个任务，请联系管理员'
  };
}

function isExcelExportRequest(text: string) {
  return /(excel|xlsx|表格|导出|下载)/i.test(text) && /(风险|问题|结果|以上|清单|输出)/.test(text);
}

function looksLikeNewTask(text: string) {
  return /(执行|运行|应用|开始|检查|校验|识别|导出|下载|excel|xlsx|上传|删除|打开)/i.test(text);
}

function explicitSkillRequest(text: string, skills: SkillDefinition[]) {
  if (!/(执行|运行|应用|开始|检查|校验|识别)/.test(text)) return undefined;
  return (
    skills.find((skill) => text.includes(skill.name)) ??
    (text.includes('冲突')
      ? skills.find((skill) => skill.id === 'skill_policy_conflict')
      : text.includes('制度与流程') || text.includes('流程校验')
        ? skills.find((skill) => skill.id === 'skill_policy_process_check')
        : text.includes('无制度依据') || text.includes('没有制度依据')
          ? skills.find((skill) => skill.id === 'skill_no_policy_basis')
          : undefined)
  );
}

function RunningSkillStrip({ skillName }: { skillName: string }) {
  return (
    <div className="running-skill-strip" aria-live="polite">
      <span className="running-dot" />
      <div>
        <strong>正在执行 {skillName}</strong>
        <p>读取已选资产、咨询知识库、调用模型并整理引用依据。</p>
      </div>
    </div>
  );
}

function taskRequestText(skill: SkillDefinition | undefined, context: WorkbenchContext, assetLabelMap: Record<string, string>) {
  const policies = context.policyIds.map((id) => assetLabelMap[id] ?? id);
  const processes = context.processIds.map((id) => assetLabelMap[id] ?? id);
  const policyText = policies.length ? `制度【${policies.join('】、【')}】` : '已选制度范围';
  const processText = processes.length ? `审批流【${processes.join('】、【')}】` : '已选审批流';
  if (!skill) return `对当前已选资产执行任务。`;
  if (skill.id === 'skill_policy_conflict') return `对${policyText}进行${skill.name}任务。`;
  if (skill.id === 'skill_policy_process_check') return `对${processText}和${policyText}进行${skill.name}任务。`;
  if (skill.id === 'skill_no_policy_basis') return `对${processText}和${policyText}进行${skill.name}任务。`;
  return `执行${skill.name}任务。`;
}

function skillName(skillId: string, skills: SkillDefinition[]) {
  return skills.find((skill) => skill.id === skillId)?.name ?? skillId;
}

function SkillResultCard({ result }: { result: SkillRunResult }) {
  return (
    <Card className="skill-result-card" size="small">
      <details className="thinking-panel">
        <summary>思考与执行过程</summary>
        <ol>
          {(result.execution_steps.length ? result.execution_steps : [result.summary]).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </details>

      {result.professional_references.length ? (
        <div className="reference-panel">
          <div className="section-label">引用依据</div>
          <div className="reference-list">
            {result.professional_references.slice(0, 6).map((reference) => (
              <ReferenceDisclosure reference={reference} result={result} key={`${reference.source}-${reference.title}`} />
            ))}
          </div>
        </div>
      ) : null}

      <section className="final-response">
        <div className="section-label">最终回复</div>
        <p>{result.final_answer || result.summary}</p>

        {result.questions.length ? (
          <div className="clarification-list">
            {result.questions.map((question) => (
              <div className="clarification-item" key={question.id}>
                <strong>{question.question}</strong>
                {question.reason ? <span>{question.reason}</span> : null}
              </div>
            ))}
          </div>
        ) : null}

        {result.findings.length && !result.questions.length ? (
          <div className="risk-stack">
            <div className="risk-count">共发现 {result.findings.length} 个风险点。</div>
            {result.findings.map((finding, index) => (
              <article className="risk-card" key={finding.id}>
                <div className="risk-heading">
                  <strong>
                    {index + 1}. {finding.title}
                  </strong>
                  <span>{finding.severity}</span>
                </div>
                <div className="risk-section">
                  <span>风险描述</span>
                  <p className="risk-detail">{finding.description}</p>
                </div>
                {finding.evidence.length ? (
                  <div className="risk-evidence-list" aria-label="制度引用">
                    <span>原文依据</span>
                    {finding.evidence.map((evidence) => (
                      <div className="risk-evidence" key={evidence.id}>
                        <span>{evidence.label}</span>
                        <em>{evidence.quote}</em>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="risk-assumption">
                  <span>判断假设</span>
                  <p>{finding.assumption || '基于当前所选制度条款和 BPMN 节点作为本次核验的有效证据范围。'}</p>
                </div>
                {finding.suggestion ? (
                  <div className="risk-section">
                    <span>优化建议</span>
                    <p className="risk-suggestion">{finding.suggestion}</p>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </Card>
  );
}

function ReferenceDisclosure({ reference, result }: { reference: ProfessionalReference; result: SkillRunResult }) {
  const [detail, setDetail] = useState<ProfessionalReference | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function loadDetail(open: boolean) {
    if (!open || loaded || loading) return;
    setLoading(true);
    try {
      const nextDetail = await api.explainProfessionalReference(
        reference,
        result.final_answer || result.summary,
        result.findings.map((finding) => `${finding.title}：${finding.description}`).join('\n')
      );
      setDetail(nextDetail);
    } catch {
      setDetail(reference);
    } finally {
      setLoaded(true);
      setLoading(false);
    }
  }

  const current = detail ?? reference;
  return (
    <details className="reference-chip" onToggle={(event) => void loadDetail(event.currentTarget.open)}>
      <summary>{reference.title || reference.source}</summary>
      <div className="reference-detail">
        <span>{reference.source}</span>
        {reference.confidence ? <em>置信度：{reference.confidence}</em> : null}
        <div>
          <strong>命中内容</strong>
          <p>{loading ? '正在读取资产库命中内容...' : current.hit_content || current.snippet || '资产库未返回可展示片段。'}</p>
        </div>
        <div>
          <strong>如何影响本次判断</strong>
          <p>{current.impact || '该依据用于提供专业判断框架；正式风险结论仍以制度条款和 BPMN 节点证据为准。'}</p>
        </div>
      </div>
    </details>
  );
}
