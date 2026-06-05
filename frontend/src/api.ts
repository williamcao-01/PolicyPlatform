import type {
  DashboardSummary,
  PolicyDocument,
  PolicyUploadAnalysis,
  ProcessDefinition,
  ProfessionalReference,
  RoleInventory,
  RoleMapping,
  SkillDefinition,
  SkillRunResult,
  TreeItem,
  WorkbenchContext
} from './types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  summary: () => getJson<DashboardSummary>('/api/dashboard/summary'),
  policyTree: () => getJson<TreeItem[]>('/api/policies/tree'),
  policy: (policyId: string) => getJson<PolicyDocument>(`/api/policies/${policyId}`),
  deletePolicy: async (policyId: string): Promise<void> => {
    const response = await fetch(`/api/policies/${policyId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Policy delete failed');
  },
  processTree: () => getJson<TreeItem[]>('/api/processes/tree'),
  process: (processId: string) => getJson<ProcessDefinition>(`/api/processes/${processId}`),
  deleteProcess: async (processId: string): Promise<void> => {
    const response = await fetch(`/api/processes/${processId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Process delete failed');
  },
  roles: () => getJson<RoleInventory>('/api/roles'),
  updateRoleMapping: async (policyRole: string, processRole: string, status = 'mapped'): Promise<RoleMapping> => {
    const response = await fetch('/api/role-mappings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ policy_role: policyRole, process_role: processRole, status })
    });
    if (!response.ok) throw new Error('Role mapping update failed');
    return response.json() as Promise<RoleMapping>;
  },
  skills: () => getJson<SkillDefinition[]>('/api/skills'),
  findings: () => getJson<import('./types').Finding[]>('/api/findings'),
  downloadFindingsExcel: async (): Promise<void> => {
    const response = await fetch('/api/exports/findings.xlsx');
    if (!response.ok) throw new Error('Findings export failed');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `待解决风险清单-${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  updateFinding: async (findingId: string, status: string): Promise<import('./types').Finding> => {
    const response = await fetch(`/api/findings/${findingId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    if (!response.ok) throw new Error('Finding update failed');
    return response.json() as Promise<import('./types').Finding>;
  },
  runSkill: async (skillId: string, context: WorkbenchContext, clarificationAnswers: Record<string, string> = {}): Promise<SkillRunResult> => {
    const response = await fetch('/api/skill-runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skill_id: skillId,
        policy_ids: context.policyIds,
        process_ids: context.processIds,
        knowledge_node_ids: [],
        clarification_answers: clarificationAnswers
      })
    });
    if (!response.ok) {
      throw new Error('任务执行失败');
    }
    return response.json() as Promise<SkillRunResult>;
  },
  explainProfessionalReference: async (reference: ProfessionalReference, question: string, context = ''): Promise<ProfessionalReference> => {
    const response = await fetch('/api/professional-references/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reference, question, context })
    });
    if (!response.ok) throw new Error('引用依据解析失败');
    return response.json() as Promise<ProfessionalReference>;
  },
  analyzePolicyUpload: async (file: File): Promise<PolicyUploadAnalysis> => {
    const body = new FormData();
    body.append('file', file);
    const response = await fetch('/api/policy-uploads/analyze', {
      method: 'POST',
      body
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<PolicyUploadAnalysis>;
  },
  savePolicyUpload: async (analysisId: string, category: string, answers: Record<string, string>): Promise<PolicyDocument> => {
    const response = await fetch(`/api/policy-uploads/${analysisId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, answers })
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<PolicyDocument>;
  }
};
