import type { SkillDefinition, WorkbenchContext } from './types';

export function validateSkillInput(skill: SkillDefinition | undefined, context: WorkbenchContext): string | null {
  if (!skill) return '未找到任务定义。';
  for (const input of skill.required_inputs) {
    const name = String(input.name);
    const label = String(input.label);
    const min = Number(input.min ?? 0);
    const max = Number(input.max ?? Number.POSITIVE_INFINITY);
    const count =
      name === 'policy_ids'
        ? context.policyIds.length
        : name === 'process_ids'
          ? context.processIds.length
          : 0;
    if (count < min) return `${skill.name}需要先点选至少 ${min} 个${label}。`;
    if (count > max) return `${skill.name}最多只能点选 ${max} 个${label}。`;
  }
  return null;
}
