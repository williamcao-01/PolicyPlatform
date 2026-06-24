import type { SkillDefinition } from '../../types';

export function isExcelExportRequest(text: string) {
  return /(excel|xlsx|表格|导出|下载)/i.test(text) && /(风险|问题|结果|以上|清单|输出)/.test(text);
}

export function looksLikeNewTask(text: string) {
  return /(执行|运行|应用|开始|检查|校验|识别|导出|下载|excel|xlsx|上传|删除|打开)/i.test(text);
}

export function explicitSkillRequest(text: string, skills: SkillDefinition[]) {
  if (!/(执行|运行|应用|开始|检查|校验|识别)/.test(text)) return undefined;
  return (
    skills.find((skill) => text.includes(skill.name)) ??
    (text.includes('冲突')
      ? skills.find((skill) => skill.id === 'skill_policy_conflict')
      : text.includes('制度与流程') || text.includes('流程校验') || text.includes('无制度依据') || text.includes('没有制度依据')
        ? skills.find((skill) => skill.id === 'skill_policy_process_check')
        : undefined)
  );
}
