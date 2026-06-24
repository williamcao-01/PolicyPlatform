import { Button, Drawer, Empty, List, Select, Space, Spin, Tag } from 'antd';
import { Settings } from 'lucide-react';
import { useState } from 'react';
import type { RoleEntry, RoleInventory, RoleMapping } from '../../types';

type Props = {
  roleInventory?: RoleInventory;
  mappingDrawerOpen: boolean;
  onMappingDrawerOpenChange: (open: boolean) => void;
  onRoleMappingUpdate: (policyRole: string, processRole: string) => void;
  onOpenPolicy: (id: string) => void;
  onOpenProcess: (id: string) => void;
};

export function RoleManagement({
  roleInventory,
  mappingDrawerOpen,
  onMappingDrawerOpenChange,
  onRoleMappingUpdate,
  onOpenPolicy,
  onOpenProcess
}: Props) {
  const [selectedRole, setSelectedRole] = useState<RoleEntry | null>(null);

  return (
    <>
      <RoleManagementBody roleInventory={roleInventory} onSelectRole={setSelectedRole} />
      <RoleSourceDrawer
        role={selectedRole}
        roleInventory={roleInventory}
        open={Boolean(selectedRole)}
        onClose={() => setSelectedRole(null)}
        onOpenPolicy={onOpenPolicy}
        onOpenProcess={onOpenProcess}
      />
      <RoleMappingDrawer
        open={mappingDrawerOpen}
        roleInventory={roleInventory}
        onClose={() => onMappingDrawerOpenChange(false)}
        onRoleMappingUpdate={onRoleMappingUpdate}
      />
    </>
  );
}

export function RoleMappingSettingsButton({ onClick }: { onClick: () => void }) {
  return <Button aria-label="设置角色映射" icon={<Settings size={15} />} size="small" type="text" onClick={onClick} />;
}

function RoleManagementBody({ roleInventory, onSelectRole }: { roleInventory?: RoleInventory; onSelectRole: (role: RoleEntry) => void }) {
  if (!roleInventory) {
    return (
      <div className="role-loading">
        <Spin size="small" />
        <span>角色加载中</span>
      </div>
    );
  }
  return (
    <div className="role-inventory">
      <div className="role-columns">
        <RoleColumn title="制度角色" roles={roleInventory.policy_roles} onSelect={onSelectRole} />
        <RoleColumn title="审批角色" roles={roleInventory.process_roles} onSelect={onSelectRole} />
      </div>
    </div>
  );
}

function RoleColumn({ title, roles, onSelect }: { title: string; roles: RoleEntry[]; onSelect: (role: RoleEntry) => void }) {
  return (
    <div className="role-column">
      <div className="role-section-title">{title}</div>
      {roles.slice(0, 18).map((role) => (
        <button className="role-node" key={role.id} type="button" onClick={() => onSelect(role)}>
          <span>{role.name}</span>
          <Tag>{role.mention_count}</Tag>
        </button>
      ))}
    </div>
  );
}

function RoleSourceDrawer({
  role,
  roleInventory,
  open,
  onClose,
  onOpenPolicy,
  onOpenProcess
}: {
  role: RoleEntry | null;
  roleInventory?: RoleInventory;
  open: boolean;
  onClose: () => void;
  onOpenPolicy: (id: string) => void;
  onOpenProcess: (id: string) => void;
}) {
  const groups = role ? groupMentionsByAsset(role) : [];
  const mappedRoles = role && roleInventory ? mappedRolesFor(role, roleInventory) : [];
  return (
    <Drawer title={role ? `${role.name} 详情` : '角色详情'} width={600} open={open} onClose={onClose}>
      {role ? (
        <Space direction="vertical" size={12} className="full-width">
          <div className="drawer-section-label">应用的{role.source === 'policy' ? '制度' : '审批流'}</div>
          {groups.map((group) => (
            <section className="role-source-group" key={group.asset_id}>
              <div className="role-source-group-header">
                <strong>{group.asset_name}</strong>
                <Button
                  size="small"
                  onClick={() => {
                    if (role.source === 'policy') onOpenPolicy(group.asset_id);
                    else onOpenProcess(group.asset_id);
                    onClose();
                  }}
                >
                  打开详情
                </Button>
              </div>
              <List
                size="small"
                dataSource={group.mentions}
                renderItem={(mention) => (
                  <List.Item>
                    <List.Item.Meta title={mention.item_label} description={mention.quote} />
                  </List.Item>
                )}
              />
            </section>
          ))}
          <div className="drawer-section-label">映射到的{role.source === 'policy' ? '审批流角色' : '制度角色'}</div>
          {mappedRoles.length ? (
            <div className="mapped-role-list">
              {mappedRoles.map((mapping) => (
                <div className="mapped-role-item" key={mapping.id}>
                  <strong>{role.source === 'policy' ? mapping.process_role : mapping.policy_role}</strong>
                  <Tag color={mapping.mapping_type === 'manual' ? 'green' : 'blue'}>
                    {mapping.mapping_type === 'manual' ? '人工调整' : `${Math.round(mapping.confidence * 100)}%`}
                  </Tag>
                  <p>{mapping.rationale}</p>
                </div>
              ))}
            </div>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无映射角色" />
          )}
        </Space>
      ) : null}
    </Drawer>
  );
}

function RoleMappingDrawer({
  open,
  roleInventory,
  onClose,
  onRoleMappingUpdate
}: {
  open: boolean;
  roleInventory?: RoleInventory;
  onClose: () => void;
  onRoleMappingUpdate: (policyRole: string, processRole: string) => void;
}) {
  const [newPolicyRole, setNewPolicyRole] = useState<string>();
  const [newProcessRole, setNewProcessRole] = useState<string>();
  const policyOptions = roleInventory?.policy_roles.map((role) => ({ value: role.name, label: role.name })) ?? [];
  const processOptions = roleInventory?.process_roles.map((role) => ({ value: role.name, label: role.name })) ?? [];
  const mappings: RoleMapping[] = roleInventory?.mappings ?? [];

  return (
    <Drawer title="制度角色与审批角色映射" width={640} open={open} onClose={onClose}>
      <Space direction="vertical" size={10} className="full-width">
        <div className="role-mapping-create">
          <Select placeholder="制度角色" value={newPolicyRole} options={policyOptions} onChange={setNewPolicyRole} />
          <Select placeholder="审批流角色" value={newProcessRole} options={processOptions} onChange={setNewProcessRole} />
          <Button
            type="primary"
            disabled={!newPolicyRole || !newProcessRole}
            onClick={() => {
              if (newPolicyRole && newProcessRole) {
                onRoleMappingUpdate(newPolicyRole, newProcessRole);
                setNewPolicyRole(undefined);
                setNewProcessRole(undefined);
              }
            }}
          >
            新增映射
          </Button>
        </div>
        {mappings.map((mapping) => (
          <div className="role-mapping-drawer-row" key={mapping.id}>
            <div>
              <strong>{mapping.policy_role}</strong>
              <p>{mapping.rationale}</p>
            </div>
            <Select value={mapping.process_role} options={processOptions} onChange={(value) => onRoleMappingUpdate(mapping.policy_role, value)} />
            <Tag color={mapping.mapping_type === 'manual' ? 'green' : 'blue'}>
              {mapping.mapping_type === 'manual' ? '人工调整' : `模型建议 ${Math.round(mapping.confidence * 100)}%`}
            </Tag>
          </div>
        ))}
        {!mappings.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无映射建议" /> : null}
      </Space>
    </Drawer>
  );
}

function mappedRolesFor(role: RoleEntry, inventory: RoleInventory) {
  return inventory.mappings.filter((mapping) =>
    role.source === 'policy' ? mapping.policy_role === role.name : mapping.process_role === role.name
  );
}

function groupMentionsByAsset(role: RoleEntry) {
  const groups = new Map<string, { asset_id: string; asset_name: string; mentions: RoleEntry['mentions'] }>();
  for (const mention of role.mentions) {
    const existing = groups.get(mention.asset_id);
    if (existing) existing.mentions.push(mention);
    else groups.set(mention.asset_id, { asset_id: mention.asset_id, asset_name: mention.asset_name, mentions: [mention] });
  }
  return Array.from(groups.values());
}
