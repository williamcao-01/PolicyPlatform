import type { SkillRunResult } from '../../types';

export type ChatEvent =
  | { id: string; type: 'message'; role: 'user' | 'assistant'; content: string }
  | { id: string; type: 'result'; result: SkillRunResult };

