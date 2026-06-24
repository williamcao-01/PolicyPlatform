import { Button, Card, Space, Tag, Tooltip } from 'antd';
import { Info, Play } from 'lucide-react';
import type { SkillDefinition, WorkbenchContext } from '../types';

type Props = {
  skills: SkillDefinition[];
  context: WorkbenchContext;
  runningSkillId: string | null;
  onSkillRun: (skillId: string) => void;
};

function inputSummary(skill: SkillDefinition) {
  if (skill.id === 'skill_policy_process_check') return '流程图与多份制度文件';
  if (skill.id === 'skill_policy_conflict') return '多份制度文件';
  if (skill.id === 'skill_upload_policy_file') return '1份制度文件';
  return skill.required_inputs.map((input) => String(input.label)).join(' + ');
}

export function SkillPanel({ skills, context, runningSkillId, onSkillRun }: Props) {
  const visibleSkills = skills.filter((skill) => skill.id !== 'skill_no_policy_basis');
  return (
    <aside className="skill-panel">
      <div className="panel-title">快速任务</div>
      <Space direction="vertical" size={12} className="full-width">
        {visibleSkills.map((skill) => (
          <Card size="small" key={skill.id} className="skill-card">
            <div className="skill-heading">
              <span>{skill.name}</span>
              <Tooltip title={skill.description}>
                <Info size={15} />
              </Tooltip>
            </div>
            <div className="skill-meta">
              <Tag color="blue">{inputSummary(skill)}</Tag>
            </div>
            <Button
              block
              icon={<Play size={15} />}
              loading={runningSkillId === skill.id}
              onClick={() => onSkillRun(skill.id)}
              type="primary"
            >
              点选应用
            </Button>
          </Card>
        ))}
      </Space>
      <div className="context-summary">
        已选：制度 {context.policyIds.length} / 流程 {context.processIds.length}
      </div>
    </aside>
  );
}
