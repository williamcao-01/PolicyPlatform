import type { SkillDefinition, WorkbenchContext } from '../../types';

export function taskRequestText(
  skill: SkillDefinition | undefined,
  context: WorkbenchContext,
  assetLabelMap: Record<string, string>
) {
  const policies = context.policyIds.map((id) => assetLabelMap[id] ?? id);
  const processes = context.processIds.map((id) => assetLabelMap[id] ?? id);
  const policyText = policies.length ? `制度【${policies.join('】、【')}】` : '已选制度范围';
  const processText = processes.length ? `审批流【${processes.join('】、【')}】` : '已选审批流';
  if (!skill) return '对当前已选资产执行任务。';
  if (skill.id === 'skill_policy_conflict') return `对${policyText}进行${skill.name}任务。`;
  if (skill.id === 'skill_policy_process_check') return `对${processText}和${policyText}进行${skill.name}任务。`;
  return `执行${skill.name}任务。`;
}

export function skillName(skillId: string, skills: SkillDefinition[]) {
  return skills.find((skill) => skill.id === skillId)?.name ?? skillId;
}
