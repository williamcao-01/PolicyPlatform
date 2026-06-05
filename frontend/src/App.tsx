import { Alert, Spin } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { AssetSidebar } from './components/AssetSidebar';
import { ChatWorkbench } from './components/ChatWorkbench';
import { SkillPanel } from './components/SkillPanel';
import { TopMetrics } from './components/TopMetrics';
import { AssetDetailDrawer } from './components/AssetDetailDrawer';
import { FindingListDrawer } from './components/FindingListDrawer';
import { PolicyUploadDrawer } from './components/PolicyUploadDrawer';
import { useSkillRunner } from './hooks/useSkillRunner';
import { useWorkbenchContext } from './hooks/useWorkbenchContext';
import { validateSkillInput } from './skillValidation';
import type { DashboardSummary, Finding, PolicyDocument, ProcessDefinition, RoleInventory, SkillDefinition, TreeItem } from './types';

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
  const { context, togglePolicy, toggleProcess, removePolicy, removeProcess } = useWorkbenchContext();
  const { runningSkillId, results, error, runSkill } = useSkillRunner();
  const assetLabelMap = useMemo(() => buildAssetLabelMap(policyTree, processTree), [policyTree, processTree]);

  useEffect(() => {
    async function load() {
      try {
        const [nextSummary, nextPolicyTree, nextProcessTree, nextRoleInventory, nextSkills] = await Promise.all([
          api.summary(),
          api.policyTree(),
          api.processTree(),
          api.roles(),
          api.skills()
        ]);
        setSummary(nextSummary);
        setPolicyTree(nextPolicyTree);
        setProcessTree(nextProcessTree);
        setRoleInventory(nextRoleInventory);
        setSkills(nextSkills);
      } catch (err) {
        const message = err instanceof Error ? err.message : '加载工作台数据失败';
        setLoadError(message);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

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
    const [nextSummary, nextPolicyTree, nextProcessTree, nextRoleInventory] = await Promise.all([
      api.summary(),
      api.policyTree(),
      api.processTree(),
      api.roles()
    ]);
    setSummary(nextSummary);
    setPolicyTree(nextPolicyTree);
    setProcessTree(nextProcessTree);
    setRoleInventory(nextRoleInventory);
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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>AI 制度治理工作台</h1>
        </div>
        <TopMetrics summary={summary} onOpenFindings={openFindingDrawer} onOpenClosedFindings={openClosedFindingDrawer} />
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
  );
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
