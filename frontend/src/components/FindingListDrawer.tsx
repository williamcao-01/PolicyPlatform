import { Button, Drawer, Empty, List, Space, Tag } from 'antd';
import { Download } from 'lucide-react';
import type { Finding } from '../types';
import { downloadFindingsWorkbook } from '../xlsxExport';

type Props = {
  findings: Finding[];
  mode: 'pending' | 'closed';
  open: boolean;
  onClose: () => void;
  onCloseFinding: (findingId: string) => void;
};

export function FindingListDrawer({ findings, mode, open, onClose, onCloseFinding }: Props) {
  const visibleFindings = findings.filter((finding) => (mode === 'closed' ? finding.status === 'closed' : finding.status !== 'closed'));
  return (
    <Drawer
      title={mode === 'closed' ? '已关闭风险清单' : '待解决风险清单'}
      width={720}
      open={open}
      onClose={onClose}
      extra={
        <Button
          aria-label="下载风险清单"
          icon={<Download size={16} />}
          type="text"
          onClick={() =>
            downloadFindingsWorkbook(
              visibleFindings,
              `${mode === 'closed' ? '已关闭风险清单' : '待解决风险清单'}-${new Date().toISOString().slice(0, 10)}.xlsx`
            )
          }
        />
      }
    >
      {visibleFindings.length === 0 ? (
        <Empty description={mode === 'closed' ? '暂无已关闭风险' : '暂无待解决风险'} />
      ) : (
        <List
          dataSource={visibleFindings}
          renderItem={(finding) => (
            <List.Item
              actions={[
                finding.status !== 'closed' ? (
                  <Button key="close" size="small" onClick={() => onCloseFinding(finding.id)}>
                    关闭问题
                  </Button>
                ) : (
                  <Tag key="closed" color="green">已关闭</Tag>
                )
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span>{finding.title}</span>
                    <Tag color={finding.severity === 'high' ? 'red' : 'orange'}>{finding.severity}</Tag>
                    <Tag>{finding.status}</Tag>
                  </Space>
                }
                description={
                  <div className="finding-list-description">
                    {mode === 'closed' ? (
                      <div className="closed-time">关闭时间：{formatClosedTime(finding.closed_at)}</div>
                    ) : null}
                    <p>{finding.description}</p>
                    {finding.evidence.map((evidence) => (
                      <blockquote key={evidence.id}>
                        <span>{evidence.label}</span>
                        <p>{evidence.quote}</p>
                      </blockquote>
                    ))}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}
    </Drawer>
  );
}

function formatClosedTime(value?: string | null) {
  if (!value) return '暂无关闭时间';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}
