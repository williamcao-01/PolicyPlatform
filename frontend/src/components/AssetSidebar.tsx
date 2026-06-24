import { Tag, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { ReactNode } from 'react';
import { useState } from 'react';
import type { RoleInventory, TreeItem, WorkbenchContext } from '../types';
import { RoleManagement, RoleMappingSettingsButton } from './assets/RoleManagement';

type Props = {
  policyTree: TreeItem[];
  processTree: TreeItem[];
  roleInventory?: RoleInventory;
  context: WorkbenchContext;
  onPolicyToggle: (id: string) => void;
  onProcessToggle: (id: string) => void;
  onRoleMappingUpdate: (policyRole: string, processRole: string) => void;
  onOpenPolicy: (id: string) => void;
  onOpenProcess: (id: string) => void;
};

export function AssetSidebar({
  policyTree,
  processTree,
  roleInventory,
  context,
  onPolicyToggle,
  onProcessToggle,
  onRoleMappingUpdate,
  onOpenPolicy,
  onOpenProcess
}: Props) {
  const [mappingDrawerOpen, setMappingDrawerOpen] = useState(false);

  return (
    <aside className="asset-sidebar">
      <AssetTreeSection
        title="制度管理"
        treeData={policyTree}
        checkedKeys={context.policyIds}
        keyPrefix="policy_"
        onToggle={onPolicyToggle}
        onOpen={onOpenPolicy}
      />
      <AssetTreeSection
        title="审批流管理"
        treeData={processTree}
        checkedKeys={context.processIds}
        keyPrefix="process_"
        onToggle={onProcessToggle}
        onOpen={onOpenProcess}
      />
      <AssetSection
        title="角色管理"
        action={<RoleMappingSettingsButton onClick={() => setMappingDrawerOpen(true)} />}
      >
        <RoleManagement
          roleInventory={roleInventory}
          mappingDrawerOpen={mappingDrawerOpen}
          onMappingDrawerOpenChange={setMappingDrawerOpen}
          onRoleMappingUpdate={onRoleMappingUpdate}
          onOpenPolicy={onOpenPolicy}
          onOpenProcess={onOpenProcess}
        />
      </AssetSection>
    </aside>
  );
}

function AssetTreeSection({
  title,
  treeData,
  checkedKeys,
  keyPrefix,
  onToggle,
  onOpen
}: {
  title: string;
  treeData: TreeItem[];
  checkedKeys: string[];
  keyPrefix: string;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <AssetSection title={title}>
      <Tree
        checkable
        defaultExpandAll
        selectable={false}
        treeData={toDataNodes(treeData, (item) => {
          if (item.key.startsWith(keyPrefix)) onOpen(item.key);
        })}
        checkedKeys={checkedKeys}
        onCheck={(_, info) => {
          const key = String(info.node.key);
          if (key.startsWith(keyPrefix)) onToggle(key);
        }}
        onDoubleClick={(_, node) => {
          const key = String(node.key);
          if (key.startsWith(keyPrefix)) onOpen(key);
        }}
      />
    </AssetSection>
  );
}

function AssetSection({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="asset-section">
      <div className="asset-section-header">
        <span>{title}</span>
        {action}
      </div>
      <div className="asset-section-body">{children}</div>
    </section>
  );
}

function toDataNodes(items: TreeItem[], onOpen: (item: TreeItem) => void): DataNode[] {
  return items.map((item) => ({
    key: item.key,
    title: (
      <span
        className="tree-node-title"
        onDoubleClick={(event) => {
          event.stopPropagation();
          onOpen(item);
        }}
      >
        <span>{item.title}</span>
        {item.children?.length ? <Tag>{countLeafNodes(item)}</Tag> : null}
      </span>
    ),
    children: item.children ? toDataNodes(item.children, onOpen) : undefined
  }));
}

function countLeafNodes(item: TreeItem): number {
  if (!item.children?.length) return 1;
  return item.children.reduce((total, child) => total + countLeafNodes(child), 0);
}
