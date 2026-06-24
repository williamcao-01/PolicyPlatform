export const PERMISSIONS = {
  WORKBENCH_VIEW: 'workbench:view',
  POLICY_VIEW: 'policy:view',
  PROCESS_VIEW: 'process:view',
  TASK_VIEW: 'task:view',
  FINDING_VIEW: 'finding:view',
  ROLE_VIEW: 'role:view',
  AI_GOVERNANCE_VIEW: 'ai_governance:view',
  SYSTEM_ADMIN: 'system:admin'
} as const;

export type PermissionCode = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export type CurrentUser = {
  id: string;
  name: string;
  department: string;
  permissions: PermissionCode[];
};

export const demoCurrentUser: CurrentUser = {
  id: 'local_admin',
  name: '系统管理员',
  department: '制度管理办公室',
  permissions: Object.values(PERMISSIONS)
};

export function hasPermission(user: CurrentUser, permission: PermissionCode) {
  return user.permissions.includes(permission);
}
