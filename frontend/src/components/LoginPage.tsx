import { Button, Select } from 'antd';
import { LogIn } from 'lucide-react';
import type { AuthPrincipal } from '../api';

export const DEMO_USERS = [
  { username: 'admin', label: '系统管理员', description: '全部后台权限' },
  { username: 'institution_admin', label: '制度管理员', description: '资产、任务、风险和 AI 审计' },
  { username: 'business_owner', label: '业务负责人', description: '资产维护、前台审查和风险查看' },
  { username: 'risk_compliance', label: '风控合规', description: '审批、风险处理和 AI 审计' },
  { username: 'auditor', label: '审计员', description: '只读资产、风险和审计' },
  { username: 'viewer', label: '只读用户', description: '只读查看' }
];

type LoginPageProps = {
  username: string;
  loading: boolean;
  error: string;
  onUsernameChange: (username: string) => void;
  onLogin: () => void;
};

export function LoginPage({ username, loading, error, onUsernameChange, onLogin }: LoginPageProps) {
  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="login-heading">
          <h1>AI 制度治理工作台</h1>
          <span>选择一个平台账号进入系统。本地演示环境暂不校验密码。</span>
        </div>
        <Select
          value={username}
          onChange={onUsernameChange}
          options={DEMO_USERS.map((user) => ({
            value: user.username,
            label: (
              <div className="login-user-option">
                <strong>{user.label}</strong>
                <span>{user.username} · {user.description}</span>
              </div>
            )
          }))}
        />
        {error ? <div className="login-error">{error}</div> : null}
        <Button block type="primary" icon={<LogIn size={16} />} loading={loading} onClick={onLogin}>
          进入平台
        </Button>
      </section>
    </main>
  );
}

export function userCanOpenAdmin(user: AuthPrincipal) {
  return user.permissions.some((permission) =>
    ['skill:audit_read', 'skill:run', 'asset:submit_review', 'asset:approve', 'asset:publish', 'asset:archive', 'rbac:manage'].includes(permission)
  );
}
