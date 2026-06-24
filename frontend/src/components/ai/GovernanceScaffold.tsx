import { Alert, Button, Empty, Spin, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';

export function GovernancePage({
  loading,
  error,
  children
}: {
  loading?: boolean;
  error?: string;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="governance-center">
        <Spin />
        <span>加载治理数据</span>
      </div>
    );
  }

  if (error) {
    return (
      <main className="production-module">
        <Alert type="error" showIcon message="AI 治理数据加载失败" description={error} />
      </main>
    );
  }

  return <main className="production-module governance-page">{children}</main>;
}

export function GovernanceSection({
  title,
  description,
  action,
  children
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="governance-section">
      <div className="governance-section-header">
        <div>
          <strong>{title}</strong>
          {description ? <span>{description}</span> : null}
        </div>
        {action}
      </div>
      <div className="governance-section-body">{children}</div>
    </section>
  );
}

export function GovernanceTable<T extends { id: string }>({
  columns,
  data,
  emptyText
}: {
  columns: ColumnsType<T>;
  data: T[];
  emptyText: string;
}) {
  return (
    <Table<T>
      columns={columns}
      dataSource={data}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} /> }}
      pagination={{ pageSize: 8, hideOnSinglePage: true }}
      rowKey="id"
      size="small"
    />
  );
}

export function CreateButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <Button type="primary" onClick={onClick}>
      {children}
    </Button>
  );
}

export function formatDateTime(value?: string | null) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

export function formatMetric(value: number) {
  if (value <= 1) return `${Math.round(value * 100)}%`;
  return String(value);
}
