import { BadgeCheck, Bot, ClipboardList, FileText, GitBranch, LayoutDashboard, Settings, ShieldAlert, UsersRound, Workflow } from 'lucide-react';
import { Button, Switch } from 'antd';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { api, type SystemSettings } from '../api';
import type { DashboardSummary, Finding, RoleInventory, TreeItem } from '../types';
import { demoCurrentUser, hasPermission, PERMISSIONS, type PermissionCode } from '../permissions';

type ModuleKey = 'workbench' | 'policies' | 'processes' | 'tasks' | 'findings' | 'roles' | 'ai' | 'system';

type NavItem = {
  key: ModuleKey;
  label: string;
  permission: PermissionCode;
  icon: typeof LayoutDashboard;
};

const NAV_ITEMS: NavItem[] = [
  { key: 'workbench', label: 'AI 工作台', permission: PERMISSIONS.WORKBENCH_VIEW, icon: LayoutDashboard },
  { key: 'policies', label: '制度资产', permission: PERMISSIONS.POLICY_VIEW, icon: FileText },
  { key: 'processes', label: '流程资产', permission: PERMISSIONS.PROCESS_VIEW, icon: Workflow },
  { key: 'tasks', label: '任务中心', permission: PERMISSIONS.TASK_VIEW, icon: ClipboardList },
  { key: 'findings', label: '风险台账', permission: PERMISSIONS.FINDING_VIEW, icon: ShieldAlert },
  { key: 'roles', label: '角色管理', permission: PERMISSIONS.ROLE_VIEW, icon: UsersRound },
  { key: 'ai', label: 'AI 治理', permission: PERMISSIONS.AI_GOVERNANCE_VIEW, icon: Bot },
  { key: 'system', label: '系统管理', permission: PERMISSIONS.SYSTEM_ADMIN, icon: Settings }
];

export type ProductionShellProps = {
  summary?: DashboardSummary;
  policyTree: TreeItem[];
  processTree: TreeItem[];
  roleInventory?: RoleInventory;
  findings: Finding[];
  children: ReactNode;
};

export function ProductionShell({ summary, policyTree, processTree, roleInventory, findings, children }: ProductionShellProps) {
  const [active, setActive] = useState<ModuleKey>('workbench');
  const visibleItems = useMemo(() => NAV_ITEMS.filter((item) => hasPermission(demoCurrentUser, item.permission)), []);

  return (
    <div className="production-layout">
      <aside className="production-nav" aria-label="主导航">
        <div className="production-brand">
          <strong>制度治理</strong>
          <span>{demoCurrentUser.department}</span>
        </div>
        <nav>
          {visibleItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={active === item.key ? 'production-nav-item active' : 'production-nav-item'}
                key={item.key}
                onClick={() => setActive(item.key)}
                type="button"
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <div className="production-main">
        <header className="production-topbar">
          <div>
            <h1>{visibleItems.find((item) => item.key === active)?.label ?? 'AI 工作台'}</h1>
            <span>{demoCurrentUser.name}</span>
          </div>
        </header>
        {active === 'workbench' ? children : (
          <ProductionModule
            active={active}
            findings={findings}
            policyTree={policyTree}
            processTree={processTree}
            roleInventory={roleInventory}
            summary={summary}
          />
        )}
      </div>
    </div>
  );
}

function ProductionModule({
  active,
  summary,
  policyTree,
  processTree,
  roleInventory,
  findings
}: {
  active: ModuleKey;
  summary?: DashboardSummary;
  policyTree: TreeItem[];
  processTree: TreeItem[];
  roleInventory?: RoleInventory;
  findings: Finding[];
}) {
  if (active === 'policies') {
    return <AssetModule title="制度资产" items={flattenTree(policyTree)} count={summary?.policy_count ?? 0} />;
  }
  if (active === 'processes') {
    return <AssetModule title="流程资产" items={flattenTree(processTree)} count={summary?.process_count ?? 0} />;
  }
  if (active === 'tasks') {
    return (
      <ModuleSurface
        rows={[
          ['任务状态机', 'queued / running / waiting_confirmation / succeeded / failed / cancelled'],
          ['执行入口', 'Skill 执行、上传分析、评测运行'],
          ['队列适配', 'RocketMQ / InMemoryQueue']
        ]}
        title="任务中心"
      />
    );
  }
  if (active === 'findings') {
    return (
      <ModuleSurface
        rows={findings.slice(0, 12).map((finding) => [finding.title, `${finding.status} · ${finding.severity}`])}
        title="风险台账"
      />
    );
  }
  if (active === 'roles') {
    return (
      <ModuleSurface
        rows={[
          ['制度角色', String(roleInventory?.policy_roles.length ?? 0)],
          ['审批角色', String(roleInventory?.process_roles.length ?? 0)],
          ['映射关系', String(roleInventory?.mappings.length ?? 0)]
        ]}
        title="角色管理"
      />
    );
  }
  if (active === 'ai') {
    return (
      <ModuleSurface
        rows={[
          ['调用审计', '请从右上角头像进入管理员后台使用真实 AI 治理功能'],
          ['评测闭环', '请从管理员后台创建数据集并运行评测'],
          ['证据约束', '制度条款或 BPMN 节点证据']
        ]}
        title="AI 治理"
      />
    );
  }
  return <SystemModule />;
}

function AssetModule({ title, count, items }: { title: string; count: number; items: Array<[string, string]> }) {
  return <ModuleSurface rows={[['资产总数', String(count)], ...items.slice(0, 16)]} title={title} />;
}

function ModuleSurface({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <main className="production-module">
      <section className="module-board">
        <div className="module-board-header">
          <strong>{title}</strong>
          <BadgeCheck size={17} />
        </div>
        <div className="module-table">
          {rows.length ? rows.map(([label, value]) => (
            <div className="module-row" key={`${label}-${value}`}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          )) : (
            <div className="module-empty">暂无数据</div>
          )}
        </div>
      </section>
    </main>
  );
}

function SystemModule() {
  const [settings, setSettings] = useState<SystemSettings>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    void api.systemSettings()
      .then((result) => {
        if (active) setSettings(result);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : '系统配置加载失败');
      });
    return () => {
      active = false;
    };
  }, []);

  async function toggleKnowledgeBase(enabled: boolean) {
    setSaving(true);
    setError('');
    try {
      const next = await api.updateKnowledgeBaseSettings({ enabled });
      setSettings((current) => current ? { ...current, knowledge_base: next } : { knowledge_base: next });
    } catch (err) {
      setError(err instanceof Error ? err.message : '知识库配置保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="production-module">
      <section className="module-board">
        <div className="module-board-header">
          <strong>系统管理</strong>
          <Settings size={17} />
        </div>
        <div className="settings-stack">
          <div className="settings-row">
            <div>
              <strong>专业知识库调用</strong>
              <span>控制 Skill 执行前是否咨询本地专业知识库。关闭后仅基于制度条款和 BPMN 节点证据。</span>
            </div>
            <Switch
              checked={settings?.knowledge_base.enabled ?? false}
              checkedChildren="开启"
              disabled={!settings || saving}
              unCheckedChildren="关闭"
              onChange={(checked) => void toggleKnowledgeBase(checked)}
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
          {error ? (
            <div className="settings-error">
              <span>{error}</span>
              <Button size="small" onClick={() => setError('')}>关闭</Button>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function flattenTree(items: TreeItem[], parent = ''): Array<[string, string]> {
  return items.flatMap((item) => {
    const path = parent ? `${parent} / ${item.title}` : item.title;
    const current: Array<[string, string]> = item.type === 'policy' || item.type === 'process' ? [[item.title, parent || item.type]] : [];
    return [...current, ...flattenTree(item.children ?? [], path)];
  });
}
