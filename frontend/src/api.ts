import type {
  DashboardSummary,
  PolicyDocument,
  PolicyUploadAnalysis,
  PolicyVersion,
  ProcessDefinition,
  ProcessVersion,
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
  login: async (username: string, password = ''): Promise<AuthResponse> => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!response.ok) throw new Error('Login failed');
    return response.json() as Promise<AuthResponse>;
  },
  me: (accessToken: string) =>
    getJsonWithAuth<AuthPrincipal>('/api/auth/me', accessToken),
  refreshToken: async (refreshToken: string): Promise<AuthResponse> => {
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (!response.ok) throw new Error('Token refresh failed');
    return response.json() as Promise<AuthResponse>;
  },
  logout: async (accessToken: string): Promise<void> => {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) throw new Error('Logout failed');
  },
  permissions: () => getJson<PermissionsResponse>('/api/permissions'),
  auditLogs: (accessToken: string) =>
    getJsonWithAuth<AuditEvent[]>('/api/audit-logs', accessToken),
  createTask: async (accessToken: string, payload: TaskCreateRequest): Promise<TaskRecord> => {
    const response = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Task create failed');
    return response.json() as Promise<TaskRecord>;
  },
  tasks: (accessToken: string) => getJsonWithAuth<TaskRecord[]>('/api/tasks', accessToken),
  task: (accessToken: string, taskId: string) => getJsonWithAuth<TaskRecord>(`/api/tasks/${taskId}`, accessToken),
  taskLogs: (accessToken: string, taskId: string) => getJsonWithAuth<TaskLog[]>(`/api/tasks/${taskId}/logs`, accessToken),
  taskResult: (accessToken: string, taskId: string) => getJsonWithAuth<Record<string, unknown>>(`/api/tasks/${taskId}/result`, accessToken),
  cancelTask: async (accessToken: string, taskId: string): Promise<TaskRecord> => {
    const response = await fetch(`/api/tasks/${taskId}/cancel`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) throw new Error('Task cancel failed');
    return response.json() as Promise<TaskRecord>;
  },
  retryTask: async (accessToken: string, taskId: string): Promise<TaskRecord> => {
    const response = await fetch(`/api/tasks/${taskId}/retry`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) throw new Error('Task retry failed');
    return response.json() as Promise<TaskRecord>;
  },
  confirmTask: async (accessToken: string, taskId: string, answers: Record<string, string>): Promise<TaskRecord> => {
    const response = await fetch(`/api/tasks/${taskId}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(answers)
    });
    if (!response.ok) throw new Error('Task confirm failed');
    return response.json() as Promise<TaskRecord>;
  },
  submitAssetReview: (accessToken: string, assetId: string) =>
    postLifecycleAction(accessToken, assetId, 'submit-review'),
  approveAsset: (accessToken: string, assetId: string) =>
    postLifecycleAction(accessToken, assetId, 'approve'),
  publishAsset: (accessToken: string, assetId: string) =>
    postLifecycleAction(accessToken, assetId, 'publish'),
  archiveAsset: (accessToken: string, assetId: string) =>
    postLifecycleAction(accessToken, assetId, 'archive'),
  systemSettings: () => getJson<SystemSettings>('/api/system/settings'),
  systemSettingsWithAuth: (accessToken: string) =>
    getJsonWithAuth<SystemSettings>('/api/system/settings', accessToken),
  updateKnowledgeBaseSettings: async (payload: KnowledgeBaseConfigUpdate): Promise<KnowledgeBaseConfig> => {
    const response = await fetch('/api/system/settings/knowledge-base', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Knowledge base settings update failed');
    return response.json() as Promise<KnowledgeBaseConfig>;
  },
  updateKnowledgeBaseSettingsWithAuth: async (accessToken: string, payload: KnowledgeBaseConfigUpdate): Promise<KnowledgeBaseConfig> => {
    const response = await fetch('/api/system/settings/knowledge-base', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Knowledge base settings update failed');
    return response.json() as Promise<KnowledgeBaseConfig>;
  },
  aiCalls: (accessToken: string) => getJsonWithAuth<AICallLog[]>('/api/ai/calls', accessToken),
  aiPrompts: (accessToken: string) => getJsonWithAuth<PromptVersion[]>('/api/ai/prompts', accessToken),
  createAiPrompt: async (accessToken: string, payload: PromptVersionCreate): Promise<PromptVersion> => {
    const response = await fetch('/api/ai/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Prompt create failed');
    return response.json() as Promise<PromptVersion>;
  },
  evaluationDatasets: (accessToken: string) => getJsonWithAuth<EvaluationDataset[]>('/api/evaluations/datasets', accessToken),
  createEvaluationDataset: async (accessToken: string, payload: EvaluationDatasetCreate): Promise<EvaluationDataset> => {
    const response = await fetch('/api/evaluations/datasets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Evaluation dataset create failed');
    return response.json() as Promise<EvaluationDataset>;
  },
  createEvaluationRun: async (accessToken: string, datasetId: string): Promise<EvaluationRun> => {
    const response = await fetch(`/api/evaluations/runs?dataset_id=${encodeURIComponent(datasetId)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) throw new Error('Evaluation run create failed');
    return response.json() as Promise<EvaluationRun>;
  },
  evaluationRun: (accessToken: string, runId: string) =>
    getJsonWithAuth<EvaluationRun>(`/api/evaluations/runs/${runId}`, accessToken),
  createFindingFeedback: async (accessToken: string, findingId: string, payload: FindingFeedbackCreate): Promise<FindingFeedback> => {
    const response = await fetch(`/api/findings/${findingId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Finding feedback create failed');
    return response.json() as Promise<FindingFeedback>;
  },
  summary: () => getJson<DashboardSummary>('/api/dashboard/summary'),
  policyTree: () => getJson<TreeItem[]>('/api/policies/tree'),
  policy: (policyId: string) => getJson<PolicyDocument>(`/api/policies/${policyId}`),
  policyVersions: (policyId: string) => getJson<PolicyVersion[]>(`/api/policies/${policyId}/versions`),
  deletePolicy: async (policyId: string): Promise<void> => {
    const response = await fetch(`/api/policies/${policyId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Policy delete failed');
  },
  processTree: () => getJson<TreeItem[]>('/api/processes/tree'),
  process: (processId: string) => getJson<ProcessDefinition>(`/api/processes/${processId}`),
  processVersions: (processId: string) => getJson<ProcessVersion[]>(`/api/processes/${processId}/versions`),
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
  downloadUploadSource: async (analysisId: string, fileName: string): Promise<void> => {
    await downloadFile(`/api/policy-uploads/${analysisId}/source`, fileName);
  },
  savePolicyUpload: async (analysisId: string, category: string, answers: Record<string, string>): Promise<PolicyDocument> => {
    const response = await fetch(`/api/policy-uploads/${analysisId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, answers })
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<PolicyDocument>;
  },
  downloadPolicySource: async (policyId: string, fileName: string): Promise<void> => {
    await downloadFile(`/api/policies/${policyId}/source`, fileName);
  },
  downloadPolicyVersionSource: async (policyId: string, versionId: string, fileName: string): Promise<void> => {
    await downloadFile(`/api/policies/${policyId}/versions/${versionId}/source`, fileName);
  }
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user: AuthPrincipal;
};

export type AuthPrincipal = {
  id: string;
  username: string;
  display_name: string;
  department: string;
  roles: string[];
  permissions: string[];
};

export type PermissionsResponse = {
  roles: string[];
  permissions: string[];
  matrix: Record<string, string[]>;
};

export type AuditEvent = {
  id: string;
  actor_id: string;
  action: string;
  object_type: string;
  object_id: string;
  request_id?: string | null;
  metadata: Record<string, string>;
  created_at: string;
};

export type TaskCreateRequest = {
  skill_id: string;
  policy_ids?: string[];
  process_ids?: string[];
  knowledge_node_ids?: string[];
  clarification_answers?: Record<string, string>;
  options?: Record<string, string>;
};

export type TaskRecord = {
  id: string;
  skill_id: string;
  status: 'queued' | 'running' | 'waiting_confirmation' | 'succeeded' | 'failed' | 'cancelled';
  requested_by: string;
  policy_ids: string[];
  process_ids: string[];
  knowledge_node_ids: string[];
  clarification_answers: Record<string, string>;
  options: Record<string, string>;
  queue_message_id?: string | null;
  result?: Record<string, unknown> | null;
  error: string;
  created_at: string;
  updated_at: string;
};

export type TaskLog = {
  id: string;
  task_id: string;
  level: string;
  message: string;
  created_at: string;
};

export type AssetLifecycleRecord = {
  id: string;
  asset_id: string;
  asset_type: string;
  status: 'draft' | 'in_review' | 'approved' | 'published' | 'archived' | 'rejected';
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  history: Array<{
    from: string;
    to: string;
    actor_id: string;
    at: string;
    reason: string;
  }>;
};

export type KnowledgeBaseConfig = {
  enabled: boolean;
  api_url: string;
  has_api_key: boolean;
};

export type KnowledgeBaseConfigUpdate = {
  enabled?: boolean;
  api_url?: string;
};

export type SystemSettings = {
  knowledge_base: KnowledgeBaseConfig;
};

export type AICallLog = {
  id: string;
  provider: string;
  model: string;
  prompt_version_id: string;
  skill_id: string;
  input_asset_version_ids: string[];
  output_hash: string;
  token_usage: Record<string, number>;
  duration_ms: number;
  status: string;
  error: string;
  created_at: string;
};

export type PromptVersion = {
  id: string;
  skill_id: string;
  version: string;
  prompt_hash: string;
  schema_hash: string;
  notes: string;
  created_by: string;
  created_at: string;
};

export type PromptVersionCreate = {
  skill_id: string;
  version: string;
  prompt_hash: string;
  schema_hash?: string;
  notes?: string;
};

export type EvaluationDataset = {
  id: string;
  name: string;
  description: string;
  sample_count: number;
  created_by: string;
  created_at: string;
};

export type EvaluationDatasetCreate = {
  name: string;
  description?: string;
  sample_count?: number;
};

export type EvaluationRun = {
  id: string;
  dataset_id: string;
  status: string;
  metrics: Record<string, number>;
  created_by: string;
  created_at: string;
  finished_at?: string | null;
};

export type FindingFeedbackCreate = {
  rating: string;
  comment?: string;
};

export type FindingFeedback = {
  id: string;
  finding_id: string;
  rating: string;
  comment: string;
  created_by: string;
  created_at: string;
};

async function getJsonWithAuth<T>(url: string, accessToken: string): Promise<T> {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json() as Promise<T>;
}

async function postLifecycleAction(
  accessToken: string,
  assetId: string,
  action: 'submit-review' | 'approve' | 'publish' | 'archive'
): Promise<AssetLifecycleRecord> {
  const response = await fetch(`/api/assets/${assetId}/${action}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Asset lifecycle action failed: ${action}`);
  return response.json() as Promise<AssetLifecycleRecord>;
}

async function downloadFile(url: string, fileName: string): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) throw new Error('文件下载失败');
  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}
