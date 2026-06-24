import { Alert, Button, Descriptions, Drawer, Form, Input, Select, Space, Switch, Table, Tabs, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeft, ClipboardList, History, KeyRound, RefreshCw, Settings, ShieldCheck, Workflow } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  api,
  type AssetLifecycleRecord,
  type AuditEvent,
  type PermissionsResponse,
  type SystemSettings,
  type TaskRecord,
  type TaskLog,
  type AuthPrincipal
} from '../../api';
import type { Finding, RoleInventory, SkillDefinition, TreeItem } from '../../types';
import { AiGovernanceModule } from '../ai/AiGovernanceModule';
import { GovernancePage, GovernanceSection, GovernanceTable, formatDateTime } from '../ai/GovernanceScaffold';

type AdminBackendModuleProps = {
  findings: Finding[];
  policyTree: TreeItem[];
  processTree: TreeItem[];
  roleInventory?: RoleInventory;
  skills: SkillDefinition[];
  accessToken: string;
  currentUser: AuthPrincipal;
  onBack: () => void;
};

type AssetOption = {
  label: string;
  value: string;
  type: 'policy' | 'process';
};

export function AdminBackendModule({ findings, policyTree, processTree, roleInventory, skills, accessToken, currentUser, onBack }: AdminBackendModuleProps) {
  const tabs = [
    hasPermission(currentUser, 'skill:audit_read')
      ? {
          key: 'ai',
          label: tabLabel(<ShieldCheck size={15} />, 'AI 治理'),
          children: <AiGovernanceModule findings={findings} accessToken={accessToken} />
        }
      : null,
    hasPermission(currentUser, 'skill:run')
      ? {
          key: 'tasks',
          label: tabLabel(<ClipboardList size={15} />, '任务中心'),
          children: <TasksAdmin accessToken={accessToken} skills={skills} policyTree={policyTree} processTree={processTree} />
        }
      : null,
    hasAnyPermission(currentUser, ['asset:submit_review', 'asset:approve', 'asset:publish', 'asset:archive'])
      ? {
          key: 'assets',
          label: tabLabel(<Workflow size={15} />, '资产生命周期'),
          children: <AssetLifecycleAdmin accessToken={accessToken} currentUser={currentUser} policyTree={policyTree} processTree={processTree} />
        }
      : null,
    hasPermission(currentUser, 'skill:audit_read')
      ? {
          key: 'audit',
          label: tabLabel(<History size={15} />, '审计日志'),
          children: <AuditAdmin accessToken={accessToken} />
        }
      : null,
    hasPermission(currentUser, 'rbac:manage')
      ? {
          key: 'permissions',
          label: tabLabel(<KeyRound size={15} />, '权限矩阵'),
          children: <PermissionsAdmin roleInventory={roleInventory} />
        }
      : null,
    hasPermission(currentUser, 'rbac:manage')
      ? {
          key: 'system',
          label: tabLabel(<Settings size={15} />, '系统设置'),
          children: <SystemSettingsAdmin accessToken={accessToken} />
        }
      : null
  ].filter((item): item is NonNullable<typeof item> => Boolean(item));

  return (
    <div className="admin-layout">
      <header className="admin-topbar">
        <div>
          <Button icon={<ArrowLeft size={15} />} onClick={onBack}>
            返回工作台
          </Button>
          <div>
            <h1>管理员后台</h1>
            <span>{currentUser.display_name} · {currentUser.roles.join(' / ')} · 后台操作会进入审计日志。</span>
          </div>
        </div>
      </header>
      <GovernancePage>
        {tabs.length ? (
          <Tabs className="governance-tabs" items={tabs} />
        ) : (
          <GovernanceSection title="暂无后台权限" description="当前账号没有可访问的后台模块。">
            <Alert type="info" showIcon message="请切换到具备后台权限的账号。" />
          </GovernanceSection>
        )}
      </GovernancePage>
    </div>
  );
}

function TasksAdmin({
  accessToken,
  skills,
  policyTree,
  processTree
}: {
  accessToken: string;
  skills: SkillDefinition[];
  policyTree: TreeItem[];
  processTree: TreeItem[];
}) {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [result, setResult] = useState<Record<string, unknown>>();
  const [selectedTask, setSelectedTask] = useState<TaskRecord>();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const policyOptions = flattenTree(policyTree).map((item) => ({ label: item.label, value: item.value }));
  const processOptions = flattenTree(processTree).map((item) => ({ label: item.label, value: item.value }));
  const skillOptions = skills.map((skill) => ({ label: skill.name, value: skill.id }));

  async function refresh() {
    if (!accessToken) return;
    setLoading(true);
    try {
      setTasks(await api.tasks(accessToken));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [accessToken]);

  async function createTask() {
    const values = await form.validateFields();
    try {
      await api.createTask(accessToken, {
        skill_id: values.skill_id,
        policy_ids: values.policy_ids ?? [],
        process_ids: values.process_ids ?? [],
        knowledge_node_ids: [],
        clarification_answers: {},
        options: {}
      });
      message.success('任务已创建');
      form.resetFields();
      await refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '任务创建失败');
    }
  }

  async function openTask(task: TaskRecord) {
    setSelectedTask(task);
    const [nextLogs, nextResult] = await Promise.all([
      api.taskLogs(accessToken, task.id),
      api.taskResult(accessToken, task.id)
    ]);
    setLogs(nextLogs);
    setResult(nextResult);
  }

  async function runAction(taskId: string, action: 'cancel' | 'retry') {
    try {
      if (action === 'cancel') await api.cancelTask(accessToken, taskId);
      else await api.retryTask(accessToken, taskId);
      await refresh();
      message.success(action === 'cancel' ? '任务已取消' : '任务已重试');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '任务操作失败');
    }
  }

  const columns: ColumnsType<TaskRecord> = [
    { title: '任务 ID', dataIndex: 'id', render: shortText },
    { title: '技能', dataIndex: 'skill_id', render: (value) => skills.find((skill) => skill.id === value)?.name ?? value },
    { title: '状态', dataIndex: 'status', render: (value) => <TaskStatusTag status={value} />, width: 150 },
    { title: '制度', dataIndex: 'policy_ids', render: (items: string[]) => items.length, width: 80 },
    { title: '流程', dataIndex: 'process_ids', render: (items: string[]) => items.length, width: 80 },
    { title: '创建时间', dataIndex: 'created_at', render: formatDateTime, width: 180 },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => void openTask(record)}>详情</Button>
          <Button size="small" disabled={record.status === 'cancelled' || record.status === 'succeeded'} onClick={() => void runAction(record.id, 'cancel')}>
            取消
          </Button>
          <Button size="small" disabled={record.status !== 'failed' && record.status !== 'cancelled'} onClick={() => void runAction(record.id, 'retry')}>
            重试
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Space direction="vertical" size={14} className="full-width">
      <GovernanceSection title="创建任务" description="对应前台点选审查 Skill 的异步化后台入口；当前前台仍走同步 /api/skill-runs，本模块用于创建和管理异步任务队列记录。">
        <Form form={form} layout="vertical" className="admin-inline-form">
          <Form.Item label="技能" name="skill_id" rules={[{ required: true, message: '请选择技能' }]}>
            <Select options={skillOptions} placeholder="选择后台任务技能" />
          </Form.Item>
          <Form.Item label="制度资产" name="policy_ids">
            <Select mode="multiple" options={policyOptions} placeholder="可选" />
          </Form.Item>
          <Form.Item label="流程资产" name="process_ids">
            <Select mode="multiple" options={processOptions} placeholder="可选" />
          </Form.Item>
          <Button type="primary" onClick={() => void createTask()}>
            创建任务
          </Button>
        </Form>
      </GovernanceSection>
      <GovernanceSection
        title="任务列表"
        description="查询、取消、重试任务，并查看任务日志和结果。"
        action={<Button icon={<RefreshCw size={15} />} loading={loading} onClick={() => void refresh()}>刷新</Button>}
      >
        <GovernanceTable columns={columns} data={tasks} emptyText="暂无任务" />
      </GovernanceSection>
      <Drawer title="任务详情" width={720} open={Boolean(selectedTask)} onClose={() => setSelectedTask(undefined)}>
        {selectedTask ? (
          <Space direction="vertical" size={14} className="full-width">
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="任务 ID">{selectedTask.id}</Descriptions.Item>
              <Descriptions.Item label="状态"><TaskStatusTag status={selectedTask.status} /></Descriptions.Item>
              <Descriptions.Item label="技能">{selectedTask.skill_id}</Descriptions.Item>
              <Descriptions.Item label="请求人">{selectedTask.requested_by}</Descriptions.Item>
              <Descriptions.Item label="队列消息">{selectedTask.queue_message_id || '无'}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{formatDateTime(selectedTask.updated_at)}</Descriptions.Item>
            </Descriptions>
            <GovernanceSection title="日志">
              <Table<TaskLog>
                columns={[
                  { title: '级别', dataIndex: 'level', width: 90 },
                  { title: '消息', dataIndex: 'message' },
                  { title: '时间', dataIndex: 'created_at', render: formatDateTime, width: 180 }
                ]}
                dataSource={logs}
                pagination={false}
                rowKey="id"
                size="small"
              />
            </GovernanceSection>
            <GovernanceSection title="结果">
              <pre className="json-preview">{JSON.stringify(result ?? {}, null, 2)}</pre>
            </GovernanceSection>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}

function AssetLifecycleAdmin({
  accessToken,
  currentUser,
  policyTree,
  processTree
}: {
  accessToken: string;
  currentUser: AuthPrincipal;
  policyTree: TreeItem[];
  processTree: TreeItem[];
}) {
  const [form] = Form.useForm();
  const [record, setRecord] = useState<AssetLifecycleRecord>();
  const [loading, setLoading] = useState(false);
  const assetOptions: AssetOption[] = [
    ...flattenTree(policyTree).map((item) => ({ ...item, type: 'policy' as const })),
    ...flattenTree(processTree).map((item) => ({ ...item, type: 'process' as const }))
  ];

  async function submit(action: 'submit-review' | 'approve' | 'publish' | 'archive') {
    const values = await form.validateFields();
    setLoading(true);
    try {
      const next = await runLifecycleAction(accessToken, values.asset_id, action);
      setRecord(next);
      message.success('资产状态已更新');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '资产状态更新失败，请检查当前状态是否允许该操作');
    } finally {
      setLoading(false);
    }
  }

  return (
    <GovernanceSection title="资产生命周期" description="对前台制度/流程资产执行真实状态流转；可执行按钮由当前账号权限决定。">
      <Space direction="vertical" size={14} className="full-width">
        <Form form={form} layout="vertical" className="admin-inline-form">
          <Form.Item label="资产" name="asset_id" rules={[{ required: true, message: '请选择资产' }]}>
            <Select
              showSearch
              options={assetOptions.map((item) => ({ label: `${item.type === 'policy' ? '制度' : '流程'} / ${item.label}`, value: item.value }))}
              optionFilterProp="label"
              placeholder="选择制度或流程资产"
            />
          </Form.Item>
          <Space wrap>
            <Button disabled={!hasPermission(currentUser, 'asset:submit_review')} loading={loading} onClick={() => void submit('submit-review')}>提交评审</Button>
            <Button disabled={!hasPermission(currentUser, 'asset:approve')} loading={loading} onClick={() => void submit('approve')}>审批通过</Button>
            <Button type="primary" disabled={!hasPermission(currentUser, 'asset:publish')} loading={loading} onClick={() => void submit('publish')}>发布</Button>
            <Button danger disabled={!hasPermission(currentUser, 'asset:archive')} loading={loading} onClick={() => void submit('archive')}>归档</Button>
          </Space>
        </Form>
        {record ? (
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="资产 ID">{record.asset_id}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color="blue">{record.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="创建人">{record.created_by}</Descriptions.Item>
            <Descriptions.Item label="更新人">{record.updated_by}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{formatDateTime(record.updated_at)}</Descriptions.Item>
            <Descriptions.Item label="历史记录">{record.history.length}</Descriptions.Item>
          </Descriptions>
        ) : null}
      </Space>
    </GovernanceSection>
  );
}

function AuditAdmin({ accessToken }: { accessToken: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    if (!accessToken) return;
    setLoading(true);
    try {
      setEvents(await api.auditLogs(accessToken));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [accessToken]);

  const columns: ColumnsType<AuditEvent> = [
    { title: '动作', dataIndex: 'action' },
    { title: '对象', render: (_, record) => `${record.object_type} / ${record.object_id}` },
    { title: '操作者', dataIndex: 'actor_id', width: 130 },
    { title: '请求 ID', dataIndex: 'request_id', render: (value) => value || '无' },
    { title: '时间', dataIndex: 'created_at', render: formatDateTime, width: 180 }
  ];

  return (
    <GovernanceSection
      title="审计日志"
      description="查看认证、任务、资产、AI 治理、系统设置等后台操作审计。"
      action={<Button icon={<RefreshCw size={15} />} loading={loading} onClick={() => void refresh()}>刷新</Button>}
    >
      <GovernanceTable columns={columns} data={events} emptyText="暂无审计日志" />
    </GovernanceSection>
  );
}

function PermissionsAdmin({ roleInventory }: { roleInventory?: RoleInventory }) {
  const [permissions, setPermissions] = useState<PermissionsResponse>();

  useEffect(() => {
    void api.permissions().then(setPermissions);
  }, []);

  const rows = permissions
    ? permissions.roles.map((role) => ({ id: role, role, permissions: permissions.matrix[role] ?? [] }))
    : [];

  return (
    <Space direction="vertical" size={14} className="full-width">
      <GovernanceSection title="权限矩阵" description="读取后端权限矩阵，展示每个角色具备的后台能力。">
        <GovernanceTable
          columns={[
            { title: '角色', dataIndex: 'role', width: 180 },
            { title: '权限', dataIndex: 'permissions', render: (items: string[]) => <Space wrap>{items.map((item) => <Tag key={item}>{item}</Tag>)}</Space> }
          ]}
          data={rows}
          emptyText="暂无权限数据"
        />
      </GovernanceSection>
      <GovernanceSection title="角色抽取状态" description="展示当前制度角色、审批角色和映射关系数量。">
        <Descriptions bordered size="small" column={3}>
          <Descriptions.Item label="制度角色">{roleInventory?.policy_roles.length ?? 0}</Descriptions.Item>
          <Descriptions.Item label="审批角色">{roleInventory?.process_roles.length ?? 0}</Descriptions.Item>
          <Descriptions.Item label="映射关系">{roleInventory?.mappings.length ?? 0}</Descriptions.Item>
        </Descriptions>
      </GovernanceSection>
    </Space>
  );
}

function SystemSettingsAdmin({ accessToken }: { accessToken: string }) {
  const [settings, setSettings] = useState<SystemSettings>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void api.systemSettingsWithAuth(accessToken)
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : '系统配置加载失败'));
  }, [accessToken]);

  async function updateKnowledgeBase(enabled: boolean) {
    setSaving(true);
    setError('');
    try {
      const next = await api.updateKnowledgeBaseSettingsWithAuth(accessToken, { enabled });
      setSettings((current) => current ? { ...current, knowledge_base: next } : { knowledge_base: next });
      message.success('系统配置已更新');
    } catch (err) {
      setError(err instanceof Error ? err.message : '系统配置保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <GovernanceSection title="系统设置" description="管理专业知识库等后台运行配置。">
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <div className="settings-stack">
        <div className="settings-row">
          <div>
            <strong>专业知识库调用</strong>
            <span>控制 Skill 执行前是否咨询本地专业知识库。</span>
          </div>
          <Switch
            checked={settings?.knowledge_base.enabled ?? false}
            checkedChildren="开启"
            disabled={!settings || saving}
            unCheckedChildren="关闭"
            onChange={(checked) => void updateKnowledgeBase(checked)}
          />
        </div>
        <div className="settings-row muted">
          <span>知识库地址</span>
          <strong>{settings?.knowledge_base.api_url ?? '未加载'}</strong>
        </div>
        <div className="settings-row muted">
          <span>API Key</span>
          <strong>{settings?.knowledge_base.has_api_key ? '已配置' : '未配置'}</strong>
        </div>
      </div>
    </GovernanceSection>
  );
}

async function runLifecycleAction(accessToken: string, assetId: string, action: 'submit-review' | 'approve' | 'publish' | 'archive') {
  if (action === 'submit-review') return api.submitAssetReview(accessToken, assetId);
  if (action === 'approve') return api.approveAsset(accessToken, assetId);
  if (action === 'publish') return api.publishAsset(accessToken, assetId);
  return api.archiveAsset(accessToken, assetId);
}

function TaskStatusTag({ status }: { status: string }) {
  const color = status === 'succeeded' ? 'green' : status === 'failed' ? 'red' : status === 'cancelled' ? 'default' : 'gold';
  return <Tag color={color}>{status}</Tag>;
}

function flattenTree(items: TreeItem[]): Array<{ label: string; value: string }> {
  return items.flatMap((item) => [
    ...(item.type === 'policy' || item.type === 'process' ? [{ label: item.title, value: item.key }] : []),
    ...flattenTree(item.children ?? [])
  ]);
}

function shortText(value?: string) {
  if (!value) return '无';
  return <span className="mono-text">{value.length > 20 ? `${value.slice(0, 20)}...` : value}</span>;
}

function tabLabel(icon: ReactNode, label: string) {
  return (
    <span className="governance-tab-label">
      {icon}
      {label}
    </span>
  );
}

function hasPermission(user: AuthPrincipal, permission: string) {
  return user.permissions.includes(permission);
}

function hasAnyPermission(user: AuthPrincipal, permissions: string[]) {
  return permissions.some((permission) => hasPermission(user, permission));
}
