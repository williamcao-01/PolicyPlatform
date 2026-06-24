import { Button, Drawer, Empty, Space, Tag } from 'antd';
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
        <div className="finding-card-list">
          {visibleFindings.map((finding, index) => (
            <article className="finding-list-card" key={finding.id}>
              <div className="finding-list-card-header">
                <div className="finding-list-card-title">
                  <span className="finding-index">{index + 1}</span>
                  <strong>{finding.title}</strong>
                </div>
                <Space>
                  <Tag color={finding.verification_status === 'uncertain' ? 'gold' : finding.severity === 'high' ? 'red' : 'orange'}>
                    {finding.verification_status === 'uncertain' ? '不确定' : finding.severity}
                  </Tag>
                  <Tag>{finding.status}</Tag>
                </Space>
              </div>
              <div className="finding-list-description">
                {mode === 'closed' ? <div className="closed-time">关闭时间：{formatClosedTime(finding.closed_at)}</div> : null}
                {finding.verification_status === 'uncertain' ? (
                  <div className="finding-verification-warning">
                    <strong>二次验证结论：不确定</strong>
                    <span>{finding.verification_note || '当前证据不足以确认该风险结论。'}</span>
                  </div>
                ) : null}
                {finding.based_on_historical_version ? (
                  <div className="finding-verification-warning">
                    <strong>该风险基于历史版本</strong>
                    <span>相关制度或审批流已产生新版本，系统不会自动重跑该风险，请按需重新执行任务。</span>
                  </div>
                ) : null}
                <p>{finding.description}</p>
                {finding.evidence.map((evidence) => (
                  <blockquote key={evidence.id}>
                    <span>{evidence.label}</span>
                    <p>{evidence.quote}</p>
                  </blockquote>
                ))}
              </div>
              <div className="finding-list-card-actions">
                {finding.status !== 'closed' ? (
                  <Button size="small" onClick={() => onCloseFinding(finding.id)}>
                    关闭问题
                  </Button>
                ) : (
                  <Tag color="green">已关闭</Tag>
                )}
              </div>
            </article>
          ))}
        </div>
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
