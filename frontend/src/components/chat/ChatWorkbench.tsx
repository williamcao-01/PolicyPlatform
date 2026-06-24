import { Alert, Button, Input, Space } from 'antd';
import { Bot, Send, UserRound } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { SkillDefinition, SkillRunResult, WorkbenchContext } from '../../types';
import { downloadFindingsWorkbook } from '../../xlsxExport';
import { explicitSkillRequest, isExcelExportRequest, looksLikeNewTask } from './chatIntents';
import { RunningSkillStrip } from './RunningSkillStrip';
import { SkillResultCard } from './SkillResultCard';
import { skillName, taskRequestText } from './taskRequestText';
import type { ChatEvent } from './types';
import './chat.css';

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
        appendUserMessage(taskRequestText(skill, context, assetLabelMap), 'user_task');
      }
    }
    previousRunningSkillId.current = runningSkillId;
  }, [assetLabelMap, context, runningSkillId, skills]);

  async function submitNaturalLanguage() {
    const text = draft.trim();
    if (!text) return;
    appendUserMessage(text);
    setDraft('');

    if (isExcelExportRequest(text)) {
      await exportRequestedResults();
      return;
    }

    if (latestResult && pendingQuestions.length > 0 && !looksLikeNewTask(text)) {
      const answers = Object.fromEntries(pendingQuestions.map((question) => [question.question, text]));
      setAnsweredQuestionResultId(latestResult.id);
      suppressNextRunAnnouncement.current = true;
      appendAssistantMessage(`已收到。下面我会把你的回复作为确认信息，继续执行“${skillName(latestResult.skill_id, skills)}”。`);
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

  async function exportRequestedResults() {
    try {
      const currentFindings = results.flatMap((result) => result.findings);
      if (currentFindings.length) {
        downloadFindingsWorkbook(currentFindings, `对话输出结果-${new Date().toISOString().slice(0, 10)}.xlsx`);
      } else {
        await onExportFindingsExcel();
      }
      appendAssistantMessage(
        currentFindings.length ? '已将当前对话中的输出结果整理为 Excel，并开始下载。' : '当前对话没有可导出的结果，已改为下载全部待解决风险清单。'
      );
    } catch {
      setEvents((items) => [...items, unsupportedMessage()]);
    }
  }

  function appendUserMessage(content: string, prefix = 'user') {
    setEvents((items) => [...items, { id: `${prefix}_${Date.now()}`, type: 'message', role: 'user', content }]);
  }

  function appendAssistantMessage(content: string) {
    setEvents((items) => [...items, { id: `assistant_${Date.now()}`, type: 'message', role: 'assistant', content }]);
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
