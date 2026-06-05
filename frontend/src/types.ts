export type DashboardSummary = {
  policy_count: number;
  process_count: number;
  knowledge_node_count: number;
  finding_count: number;
  pending_review_count: number;
  closed_count: number;
};

export type TreeItem = {
  key: string;
  title: string;
  type: string;
  children?: TreeItem[];
};

export type SkillDefinition = {
  id: string;
  name: string;
  description: string;
  required_inputs: Array<Record<string, unknown>>;
  output_types: string[];
  can_update_assets: boolean;
};

export type Evidence = {
  id: string;
  source_type: 'policy_clause' | 'bpmn_node' | 'knowledge_node';
  source_id: string;
  label: string;
  quote: string;
};

export type ProfessionalReference = {
  source: string;
  title: string;
  snippet: string;
  confidence?: string | null;
  reference_id?: string;
  source_kind?: string;
  path?: string;
  hit_content?: string;
  impact?: string;
};

export type ClarificationQuestion = {
  id: string;
  question: string;
  reason: string;
  blocking: boolean;
  source: string;
};

export type Finding = {
  id: string;
  finding_type: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: string;
  closed_at?: string | null;
  confidence: number;
  skill_id: string;
  target_ids: string[];
  evidence: Evidence[];
  assumption?: string;
  suggestion: string;
  professional_references: ProfessionalReference[];
};

export type SkillRunResult = {
  id: string;
  skill_id: string;
  status: 'completed' | 'failed';
  summary: string;
  execution_steps: string[];
  final_answer: string;
  findings: Finding[];
  hook_event_ids: string[];
  questions: ClarificationQuestion[];
  professional_references: ProfessionalReference[];
};

export type RoleMention = {
  asset_id: string;
  asset_name: string;
  item_id: string;
  item_label: string;
  quote: string;
};

export type RoleEntry = {
  id: string;
  name: string;
  source: 'policy' | 'process';
  mention_count: number;
  mentions: RoleMention[];
};

export type RoleMapping = {
  id: string;
  policy_role: string;
  process_role: string;
  confidence: number;
  mapping_type: 'auto' | 'manual';
  status: 'mapped' | 'unmapped' | 'ignored';
  rationale: string;
};

export type RoleInventory = {
  policy_roles: RoleEntry[];
  process_roles: RoleEntry[];
  mappings: RoleMapping[];
};

export type PolicyClause = {
  id: string;
  policy_id: string;
  clause_no: string;
  title: string;
  content: string;
  parent_id?: string | null;
  order_index: number;
};

export type PolicyDocument = {
  id: string;
  name: string;
  code: string;
  version: string;
  category: string;
  org_scope: string;
  status: string;
  effective_date: string;
  clauses: PolicyClause[];
};

export type ProcessNode = {
  id: string;
  process_id: string;
  bpmn_element_id: string;
  name: string;
  role: string;
  action: string;
  condition?: string | null;
  order_index: number;
};

export type ProcessDefinition = {
  id: string;
  name: string;
  code: string;
  business_domain: string;
  org_scope: string;
  status: string;
  nodes: ProcessNode[];
  asset: {
    id: string;
    process_id: string;
    file_name: string;
    bpmn_xml: string;
  };
};

export type WorkbenchContext = {
  policyIds: string[];
  processIds: string[];
};

export type PolicyUploadAnalysis = {
  analysis_id: string;
  file_name: string;
  suitable: boolean;
  rejection_level?: 'none' | 'hard';
  can_force_upload?: boolean;
  reasons: string[];
  suggestions: string[];
  questions: string[];
  metadata: Record<string, string>;
  clauses: PolicyClause[];
  concepts: Array<{ node_type: string; name: string }>;
  professional_references: ProfessionalReference[];
  professional_questions: ClarificationQuestion[];
  text_preview: string;
};
