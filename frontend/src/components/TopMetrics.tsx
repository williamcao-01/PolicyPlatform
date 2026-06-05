import { BadgeCheck, FileText, GitBranch, ShieldAlert, Workflow } from 'lucide-react';
import type { DashboardSummary } from '../types';

type Props = {
  summary?: DashboardSummary;
  onOpenFindings?: () => void;
  onOpenClosedFindings?: () => void;
};

export function TopMetrics({ summary, onOpenFindings, onOpenClosedFindings }: Props) {
  const metrics = [
    { label: '收录制度', value: summary?.policy_count ?? '-', icon: FileText },
    { label: 'BPMN 流程', value: summary?.process_count ?? '-', icon: Workflow },
    { label: '角色数量', value: summary?.knowledge_node_count ?? '-', icon: GitBranch },
    { label: '待解决风险', value: summary?.pending_review_count ?? '-', icon: ShieldAlert, onClick: onOpenFindings },
    { label: '已关闭', value: summary?.closed_count ?? '-', icon: BadgeCheck, onClick: onOpenClosedFindings }
  ];

  return (
    <div className="top-metrics">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <button
            className={metric.onClick ? 'metric clickable' : 'metric'}
            key={metric.label}
            onClick={metric.onClick}
            type="button"
          >
            <Icon size={18} />
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </button>
        );
      })}
    </div>
  );
}
