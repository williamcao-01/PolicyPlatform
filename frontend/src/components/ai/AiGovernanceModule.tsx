import { Alert, Button, Descriptions, Drawer, Form, Input, InputNumber, Select, Space, Tabs, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Bot, ClipboardCheck, FilePlus2, MessageSquarePlus, Play, RefreshCw, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { api, type AICallLog, type AuditEvent, type EvaluationDataset, type EvaluationRun, type FindingFeedbackCreate, type PromptVersion } from '../../api';
import type { Finding } from '../../types';
import { CreateButton, GovernancePage, GovernanceSection, GovernanceTable, formatDateTime, formatMetric } from './GovernanceScaffold';

type AiGovernanceModuleProps = {
  findings: Finding[];
  accessToken: string;
};

export function AiGovernanceModule({ findings, accessToken }: AiGovernanceModuleProps) {
  const [calls, setCalls] = useState<AICallLog[]>([]);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    if (!accessToken) return;
    setLoading(true);
    setError('');
    try {
      const [nextCalls, nextPrompts, nextDatasets, nextAuditLogs] = await Promise.all([
        api.aiCalls(accessToken),
        api.aiPrompts(accessToken),
        api.evaluationDatasets(accessToken),
        api.auditLogs(accessToken)
      ]);
      setCalls(nextCalls);
      setPrompts(nextPrompts);
      setDatasets(nextDatasets);
      setAuditLogs(nextAuditLogs.filter((item) => item.action.startsWith('ai.') || item.action.startsWith('finding.feedback')));
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [accessToken]);

  async function createRun(datasetId: string) {
    if (!accessToken) return;
    const run = await api.createEvaluationRun(accessToken, datasetId);
    setRuns((items) => [run, ...items.filter((item) => item.id !== run.id)]);
    message.success('评测运行已完成');
  }

  return (
    <GovernancePage loading={loading} error={error}>
      <Tabs
        className="governance-tabs"
        items={[
          {
            key: 'calls',
            label: tabLabel(<Bot size={15} />, '调用审计'),
            children: <CallsTab calls={calls} onRefresh={refresh} />
          },
          {
            key: 'prompts',
            label: tabLabel(<FilePlus2 size={15} />, 'Prompt 版本'),
            children: <PromptsTab accessToken={accessToken} prompts={prompts} onCreated={refresh} />
          },
          {
            key: 'evaluations',
            label: tabLabel(<ClipboardCheck size={15} />, '评测闭环'),
            children: <EvaluationsTab accessToken={accessToken} datasets={datasets} runs={runs} onCreated={refresh} onRun={createRun} />
          },
          {
            key: 'feedback',
            label: tabLabel(<MessageSquarePlus size={15} />, '风险反馈'),
            children: <FeedbackTab accessToken={accessToken} findings={findings} />
          },
          {
            key: 'audit',
            label: tabLabel(<ShieldCheck size={15} />, '治理审计'),
            children: <AuditTab auditLogs={auditLogs} onRefresh={refresh} />
          }
        ]}
      />
    </GovernancePage>
  );
}

function CallsTab({ calls, onRefresh }: { calls: AICallLog[]; onRefresh: () => Promise<void> }) {
  const columns: ColumnsType<AICallLog> = [
    { title: '提供方', dataIndex: 'provider', width: 110 },
    { title: '模型', dataIndex: 'model', width: 150 },
    { title: '技能', dataIndex: 'skill_id', render: valueOrDash },
    { title: 'Prompt 版本', dataIndex: 'prompt_version_id', render: valueOrDash },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'succeeded' ? 'green' : 'red'}>{value}</Tag>, width: 110 },
    { title: '耗时', dataIndex: 'duration_ms', render: (value) => `${value} ms`, width: 100 },
    { title: 'Token', dataIndex: 'token_usage', render: (value: Record<string, number>) => Object.entries(value).map(([key, item]) => `${key}:${item}`).join(' / ') || '无' },
    { title: '时间', dataIndex: 'created_at', render: formatDateTime, width: 180 }
  ];
  return (
    <GovernanceSection
      title="AI 调用审计"
      description="对应前台点选审查 Skill 后的模型调用记录；只有启用真实 LLM 时才会产生模型调用数据。"
      action={<Button icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>刷新</Button>}
    >
      <GovernanceTable columns={columns} data={calls} emptyText="暂无 AI 调用记录" />
    </GovernanceSection>
  );
}

function PromptsTab({
  accessToken,
  prompts,
  onCreated
}: {
  accessToken: string;
  prompts: PromptVersion[];
  onCreated: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const columns: ColumnsType<PromptVersion> = [
    { title: '技能', dataIndex: 'skill_id' },
    { title: '版本', dataIndex: 'version', width: 110 },
    { title: 'Prompt Hash', dataIndex: 'prompt_hash', render: shortHash },
    { title: 'Schema Hash', dataIndex: 'schema_hash', render: shortHash },
    { title: '备注', dataIndex: 'notes', render: valueOrDash },
    { title: '创建人', dataIndex: 'created_by', width: 120 },
    { title: '创建时间', dataIndex: 'created_at', render: formatDateTime, width: 180 }
  ];

  async function submit() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.createAiPrompt(accessToken, values);
      message.success('Prompt 版本已创建');
      form.resetFields();
      setOpen(false);
      await onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <GovernanceSection
        title="Prompt 版本管理"
        description="登记前台审查 Skill 使用的 prompt.md/schema.json 版本哈希。当前用于审计追溯，不会自动替换运行时文件。"
        action={<CreateButton onClick={() => setOpen(true)}>新增版本</CreateButton>}
      >
        <GovernanceTable columns={columns} data={prompts} emptyText="暂无 Prompt 版本" />
      </GovernanceSection>
      <Drawer title="新增 Prompt 版本" width={520} open={open} onClose={() => setOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item label="技能 ID" name="skill_id" rules={[{ required: true, message: '请输入技能 ID' }]}>
            <Input placeholder="skill_policy_conflict" />
          </Form.Item>
          <Form.Item label="版本号" name="version" rules={[{ required: true, message: '请输入版本号' }]}>
            <Input placeholder="v1.0.0" />
          </Form.Item>
          <Form.Item label="Prompt Hash" name="prompt_hash" rules={[{ required: true, message: '请输入 Prompt Hash' }]}>
            <Input placeholder="sha256:..." />
          </Form.Item>
          <Form.Item label="Schema Hash" name="schema_hash">
            <Input placeholder="sha256:..." />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={4} placeholder="版本变更说明" />
          </Form.Item>
          <Button block type="primary" loading={saving} onClick={() => void submit()}>
            保存版本
          </Button>
        </Form>
      </Drawer>
    </>
  );
}

function EvaluationsTab({
  accessToken,
  datasets,
  runs,
  onCreated,
  onRun
}: {
  accessToken: string;
  datasets: EvaluationDataset[];
  runs: EvaluationRun[];
  onCreated: () => Promise<void>;
  onRun: (datasetId: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun>();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const datasetNameById = useMemo(() => Object.fromEntries(datasets.map((item) => [item.id, item.name])), [datasets]);
  const datasetColumns: ColumnsType<EvaluationDataset> = [
    { title: '数据集', dataIndex: 'name' },
    { title: '描述', dataIndex: 'description', render: valueOrDash },
    { title: '样本数', dataIndex: 'sample_count', width: 90 },
    { title: '创建人', dataIndex: 'created_by', width: 120 },
    { title: '创建时间', dataIndex: 'created_at', render: formatDateTime, width: 180 },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Button icon={<Play size={14} />} size="small" onClick={() => void onRun(record.id)}>
          运行
        </Button>
      )
    }
  ];
  const runColumns: ColumnsType<EvaluationRun> = [
    { title: '数据集', dataIndex: 'dataset_id', render: (value) => datasetNameById[value] ?? value },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'succeeded' ? 'green' : 'gold'}>{value}</Tag>, width: 100 },
    { title: '指标', dataIndex: 'metrics', render: (metrics: Record<string, number>) => Object.entries(metrics).map(([key, value]) => `${key}: ${formatMetric(value)}`).join(' / ') },
    { title: '创建时间', dataIndex: 'created_at', render: formatDateTime, width: 180 },
    {
      title: '详情',
      key: 'detail',
      width: 90,
      render: (_, record) => <Button size="small" onClick={() => setSelectedRun(record)}>查看</Button>
    }
  ];

  async function submit() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.createEvaluationDataset(accessToken, values);
      message.success('评测数据集已创建');
      form.resetFields();
      setOpen(false);
      await onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Space direction="vertical" size={14} className="full-width">
      <GovernanceSection
        title="评测数据集"
        description="维护用于回归测试 AI 审查质量的样本集合。它服务于前台审查 Skill 的质量验证，不会直接影响用户运行结果。"
        action={<CreateButton onClick={() => setOpen(true)}>新增数据集</CreateButton>}
      >
        <GovernanceTable columns={datasetColumns} data={datasets} emptyText="暂无评测数据集" />
      </GovernanceSection>
      <GovernanceSection title="评测运行" description="从数据集触发一次后端评测，记录 schema 合规、证据准确率等指标。">
        <GovernanceTable columns={runColumns} data={runs} emptyText="本页暂无新触发的评测运行" />
      </GovernanceSection>
      <Drawer title="新增评测数据集" width={520} open={open} onClose={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ sample_count: 0 }}>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入数据集名称' }]}>
            <Input placeholder="审批权限回归集" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={4} placeholder="覆盖范围、样本来源和评测目标" />
          </Form.Item>
          <Form.Item label="样本数" name="sample_count">
            <InputNumber min={0} className="full-width" />
          </Form.Item>
          <Button block type="primary" loading={saving} onClick={() => void submit()}>
            保存数据集
          </Button>
        </Form>
      </Drawer>
      <RunDetailDrawer run={selectedRun} datasetName={selectedRun ? datasetNameById[selectedRun.dataset_id] : ''} onClose={() => setSelectedRun(undefined)} />
    </Space>
  );
}

function FeedbackTab({ accessToken, findings }: { accessToken: string; findings: Finding[] }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const findingOptions = findings.map((item) => ({ label: `${item.title} · ${item.status}`, value: item.id }));

  async function submit() {
    const values = await form.validateFields();
    const payload: FindingFeedbackCreate = { rating: values.rating, comment: values.comment ?? '' };
    setSaving(true);
    try {
      await api.createFindingFeedback(accessToken, values.finding_id, payload);
      message.success('风险反馈已提交');
      form.resetFields();
    } finally {
      setSaving(false);
    }
  }

  return (
    <GovernanceSection title="Finding 反馈" description="对前台审查产生的风险 finding 做人工评价，作为后续 prompt 调整和评测样本建设依据。">
      {!findings.length ? (
        <Alert type="info" showIcon message="暂无风险记录" description="运行审查技能产生 finding 后，可在这里提交反馈。" />
      ) : (
        <Form form={form} layout="vertical" className="governance-form">
          <Form.Item label="风险记录" name="finding_id" rules={[{ required: true, message: '请选择风险记录' }]}>
            <Select showSearch options={findingOptions} optionFilterProp="label" placeholder="选择需要反馈的 finding" />
          </Form.Item>
          <Form.Item label="评价" name="rating" rules={[{ required: true, message: '请选择评价' }]}>
            <Select
              options={[
                { label: '准确', value: 'accurate' },
                { label: '部分准确', value: 'partially_accurate' },
                { label: '不准确', value: 'inaccurate' }
              ]}
              placeholder="选择评价"
            />
          </Form.Item>
          <Form.Item label="说明" name="comment">
            <Input.TextArea rows={5} placeholder="记录证据问题、风险描述问题或建议改进方向" />
          </Form.Item>
          <Button type="primary" loading={saving} onClick={() => void submit()}>
            提交反馈
          </Button>
        </Form>
      )}
    </GovernanceSection>
  );
}

function AuditTab({ auditLogs, onRefresh }: { auditLogs: AuditEvent[]; onRefresh: () => Promise<void> }) {
  const columns: ColumnsType<AuditEvent> = [
    { title: '动作', dataIndex: 'action' },
    { title: '对象类型', dataIndex: 'object_type', width: 130 },
    { title: '对象 ID', dataIndex: 'object_id', render: shortHash },
    { title: '操作者', dataIndex: 'actor_id', width: 120 },
    { title: '请求 ID', dataIndex: 'request_id', render: valueOrDash },
    { title: '时间', dataIndex: 'created_at', render: formatDateTime, width: 180 }
  ];
  return (
    <GovernanceSection
      title="AI 治理审计"
      description="聚合 AI prompt、评测和 finding 反馈相关审计事件。"
      action={<Button icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>刷新</Button>}
    >
      <GovernanceTable columns={columns} data={auditLogs} emptyText="暂无 AI 治理审计记录" />
    </GovernanceSection>
  );
}

function RunDetailDrawer({ run, datasetName, onClose }: { run?: EvaluationRun; datasetName?: string; onClose: () => void }) {
  return (
    <Drawer title="评测运行详情" width={520} open={Boolean(run)} onClose={onClose}>
      {run ? (
        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label="运行 ID">{run.id}</Descriptions.Item>
          <Descriptions.Item label="数据集">{datasetName || run.dataset_id}</Descriptions.Item>
          <Descriptions.Item label="状态">{run.status}</Descriptions.Item>
          <Descriptions.Item label="创建人">{run.created_by}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDateTime(run.created_at)}</Descriptions.Item>
          <Descriptions.Item label="完成时间">{formatDateTime(run.finished_at)}</Descriptions.Item>
          <Descriptions.Item label="指标">
            <Space wrap>
              {Object.entries(run.metrics).map(([key, value]) => (
                <Tag color="blue" key={key}>{key}: {formatMetric(value)}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
        </Descriptions>
      ) : null}
    </Drawer>
  );
}

function tabLabel(icon: ReactNode, label: string) {
  return (
    <span className="governance-tab-label">
      {icon}
      {label}
    </span>
  );
}

function shortHash(value?: string) {
  if (!value) return '无';
  return <span className="mono-text">{value.length > 18 ? `${value.slice(0, 18)}...` : value}</span>;
}

function valueOrDash(value?: string) {
  return value || '无';
}
