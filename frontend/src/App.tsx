import { Alert, Avatar, Dropdown, Spin, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { api, type AuthPrincipal, type AuthResponse } from './api';
import { AssetSidebar } from './components/AssetSidebar';
import { ChatWorkbench } from './components/ChatWorkbench';
import { SkillPanel } from './components/SkillPanel';
import { TopMetrics } from './components/TopMetrics';
import { AssetDetailDrawer } from './components/AssetDetailDrawer';
import { FindingListDrawer } from './components/FindingListDrawer';
import { PolicyUploadDrawer } from './components/PolicyUploadDrawer';
import { AdminBackendModule } from './components/admin/AdminBackendModule';
import { LoginPage, userCanOpenAdmin } from './components/LoginPage';
import { useSkillRunner } from './hooks/useSkillRunner';
import { useWorkbenchContext } from './hooks/useWorkbenchContext';
import { validateSkillInput } from './skillValidation';
import type { DashboardSummary, Finding, PolicyDocument, ProcessDefinition, RoleInventory, SkillDefinition, TreeItem } from './types';
import { Settings, LogOut, UserRound } from 'lucide-react';

const AUTH_STORAGE_KEY = 'policy_governance_auth';

export default function App() {
  const [summary, setSummary] = useState<DashboardSummary>();
  const [policyTree, setPolicyTree] = useState<TreeItem[]>([]);
  const [processTree, setProcessTree] = useState<TreeItem[]>([]);
  const [roleInventory, setRoleInventory] = useState<RoleInventory>();
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [openPolicy, setOpenPolicy] = useState<PolicyDocument>();
  const [openProcess, setOpenProcess] = useState<ProcessDefinition>();
  const [findingDrawerOpen, setFindingDrawerOpen] = useState(false);
  const [findingDrawerMode, setFindingDrawerMode] = useState<'pending' | 'closed'>('pending');
  const [findings, setFindings] = useState<Finding[]>([]);
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginUsername, setLoginUsername] = useState('admin');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const { context, togglePolicy, toggleProcess, removePolicy, removeProcess } = useWorkbenchContext();
  const { runningSkillId, results, error, runSkill } = useSkillRunner();
  const assetLabelMap = useMemo(() => buildAssetLabelMap(policyTree, processTree), [policyTree, processTree]);

  useEffect(() => {
    async function restoreAuth() {
      const stored = readStoredAuth();
      if (!stored?.access_token) {
        setAuthChecked(true);
        return;
      }
      try {
        const user = await api.me(stored.access_token);
        setAuth({ ...stored, user });
      } catch {
        window.localStorage.removeItem(AUTH_STORAGE_KEY);
      } finally {
        setAuthChecked(true);
      }
    }
    void restoreAuth();
  }, []);

  useEffect(() => {
    if (!auth) return;
    async function load() {
      try {
        const [nextSummary, nextPolicyTree, nextProcessTree, nextSkills, nextFindings] = await Promise.all([
          api.summary(),
          api.policyTree(),
          api.processTree(),
          api.skills(),
          api.findings()
        ]);
        setSummary(nextSummary);
        setPolicyTree(nextPolicyTree);
        setProcessTree(nextProcessTree);
        setSkills(nextSkills);
        setFindings(nextFindings);
        void loadRoleInventory();
      } catch (err) {
        const message = err instanceof Error ? err.message : '加载工作台数据失败';
        setLoadError(message);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [auth]);

  async function handleLogin() {
    setLoginLoading(true);
    setLoginError('');
    try {
      const next = await api.login(loginUsername);
      window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(next));
      setAuth(next);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleLogout() {
    try {
      if (auth?.access_token) await api.logout(auth.access_token);
    } catch {
      // Local demo logout should still clear the browser session.
    }
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setAuth(null);
    setAdminOpen(false);
    setLoading(true);
    message.success('已登出');
  }

  if (!authChecked) {
    return (
      <div className="loading-screen">
        <Spin size="large" />
      </div>
    );
  }

  if (!auth) {
    return (
      <LoginPage
        username={loginUsername}
        loading={loginLoading}
        error={loginError}
        onUsernameChange={setLoginUsername}
        onLogin={handleLogin}
      />
    );
  }

  async function loadRoleInventory() {
    try {
      setRoleInventory(await api.roles());
    } catch {
      setRoleInventory(undefined);
    }
  }

  async function handleSkillRun(skillId: string, clarificationAnswers: Record<string, string> = {}) {
    if (skillId === 'skill_upload_policy_file') {
      setUploadDrawerOpen(true);
      return;
    }
    const skill = skills.find((item) => item.id === skillId);
    const message = validateSkillInput(skill, context);
    if (message) {
      setValidationError(message);
      return;
    }
    setValidationError(null);
    await runSkill(skillId, context, clarificationAnswers);
    const nextSummary = await api.summary();
    setSummary(nextSummary);
    if (findingDrawerOpen) setFindings(await api.findings());
  }

  async function handleRoleMappingUpdate(policyRole: string, processRole: string) {
    await api.updateRoleMapping(policyRole, processRole);
    setRoleInventory(await api.roles());
    setSummary(await api.summary());
  }

  async function handleOpenPolicy(policyId: string) {
    setOpenPolicy(await api.policy(policyId));
    setOpenProcess(undefined);
  }

  async function handleOpenProcess(processId: string) {
    setOpenProcess(await api.process(processId));
    setOpenPolicy(undefined);
  }

  async function openFindingDrawer() {
    setFindingDrawerMode('pending');
    setFindings(await api.findings());
    setFindingDrawerOpen(true);
  }

  async function openClosedFindingDrawer() {
    setFindingDrawerMode('closed');
    setFindings(await api.findings());
    setFindingDrawerOpen(true);
  }

  async function closeFinding(findingId: string) {
    await api.updateFinding(findingId, 'closed');
    setFindings(await api.findings());
    setSummary(await api.summary());
  }

  async function refreshAssets() {
    const [nextSummary, nextPolicyTree, nextProcessTree] = await Promise.all([
      api.summary(),
      api.policyTree(),
      api.processTree()
    ]);
    setSummary(nextSummary);
    setPolicyTree(nextPolicyTree);
    setProcessTree(nextProcessTree);
    void loadRoleInventory();
  }

  async function handleDeletePolicy(policyId: string) {
    await api.deletePolicy(policyId);
    removePolicy(policyId);
    setOpenPolicy(undefined);
    await refreshAssets();
  }

  async function handleDeleteProcess(processId: string) {
    await api.deleteProcess(processId);
    removeProcess(processId);
    setOpenProcess(undefined);
    await refreshAssets();
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <Spin size="large" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="loading-screen">
        <Alert type="error" showIcon message="无法加载 Demo API" description={loadError} />
      </div>
    );
  }

  if (adminOpen) {
    return (
      <AdminBackendModule
        findings={findings}
        policyTree={policyTree}
        processTree={processTree}
        roleInventory={roleInventory}
        skills={skills}
        accessToken={auth.access_token}
        currentUser={auth.user}
        onBack={() => setAdminOpen(false)}
      />
    );
  }

  return (
    <div className="standalone-shell">
      <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>AI 制度治理工作台</h1>
        </div>
        <div className="header-metrics-wrap">
          <TopMetrics summary={summary} onOpenFindings={openFindingDrawer} onOpenClosedFindings={openClosedFindingDrawer} />
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                ...(userCanOpenAdmin(auth.user) ? [{ key: 'admin', icon: <Settings size={15} />, label: '管理员后台' }] : []),
                { key: 'logout', icon: <LogOut size={15} />, label: '登出' }
              ],
              onClick: ({ key }) => {
                if (key === 'admin') {
                  setAdminOpen(true);
                  return;
                }
                void handleLogout();
              }
            }}
          >
            <button className="avatar-menu-button" type="button" aria-label="用户菜单">
              <Avatar icon={<UserRound size={18} />} />
              <span>{auth.user.display_name}</span>
            </button>
          </Dropdown>
        </div>
      </header>

      <section className="workbench-grid">
        <AssetSidebar
          policyTree={policyTree}
          processTree={processTree}
          roleInventory={roleInventory}
          context={context}
          onPolicyToggle={togglePolicy}
          onProcessToggle={toggleProcess}
          onRoleMappingUpdate={handleRoleMappingUpdate}
          onOpenPolicy={handleOpenPolicy}
          onOpenProcess={handleOpenProcess}
        />
        <ChatWorkbench
          skills={skills}
          context={context}
          assetLabelMap={assetLabelMap}
          results={results}
          runningSkillId={runningSkillId}
          error={validationError ?? error}
          onSkillRun={handleSkillRun}
          onExportFindingsExcel={api.downloadFindingsExcel}
        />
        <SkillPanel skills={skills} context={context} runningSkillId={runningSkillId} onSkillRun={handleSkillRun} />
      </section>
      <AssetDetailDrawer
        policy={openPolicy}
        process={openProcess}
        roleInventory={roleInventory}
        open={Boolean(openPolicy || openProcess)}
        onClose={() => {
          setOpenPolicy(undefined);
          setOpenProcess(undefined);
        }}
        onDeletePolicy={handleDeletePolicy}
        onDeleteProcess={handleDeleteProcess}
      />
      <FindingListDrawer
        findings={findings}
        mode={findingDrawerMode}
        open={findingDrawerOpen}
        onClose={() => setFindingDrawerOpen(false)}
        onCloseFinding={closeFinding}
      />
      <PolicyUploadDrawer
        open={uploadDrawerOpen}
        policyTree={policyTree}
        onClose={() => setUploadDrawerOpen(false)}
        onSaved={async () => {
          await refreshAssets();
        }}
      />
      </div>
    </div>
  );
}

function readStoredAuth(): AuthResponse | null {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthResponse) : null;
  } catch {
    return null;
  }
}

function buildAssetLabelMap(policyTree: TreeItem[], processTree: TreeItem[]) {
  const labels: Record<string, string> = {};
  const visit = (items: TreeItem[]) => {
    for (const item of items) {
      if (item.type === 'policy' || item.type === 'process') labels[item.key] = item.title;
      if (item.children) visit(item.children);
    }
  };
  visit(policyTree);
  visit(processTree);
  return labels;
}
