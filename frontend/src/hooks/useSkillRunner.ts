import { useState } from 'react';
import { api } from '../api';
import type { SkillRunResult, WorkbenchContext } from '../types';

export function useSkillRunner() {
  const [runningSkillId, setRunningSkillId] = useState<string | null>(null);
  const [results, setResults] = useState<SkillRunResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function runSkill(skillId: string, context: WorkbenchContext, clarificationAnswers: Record<string, string> = {}) {
    setRunningSkillId(skillId);
    setError(null);
    try {
      const result = await api.runSkill(skillId, context, clarificationAnswers);
      setResults((items) => [...items, result]);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : '任务执行失败';
      setError(message);
      throw err;
    } finally {
      setRunningSkillId(null);
    }
  }

  return { runningSkillId, results, error, runSkill };
}
