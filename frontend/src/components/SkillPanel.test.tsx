import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SkillPanel } from './SkillPanel';
import type { SkillDefinition } from '../types';

const skills: SkillDefinition[] = [
  {
    id: 'skill_policy_conflict',
    name: '多制度冲突检查',
    description: '比对多份制度。',
    required_inputs: [{ label: '制度文件' }],
    output_types: ['finding'],
    can_update_assets: false
  },
  {
    id: 'skill_policy_process_check',
    name: '制度与流程校验',
    description: '检查制度与流程。',
    required_inputs: [{ label: '制度文件' }, { label: 'BPMN 流程' }],
    output_types: ['finding'],
    can_update_assets: true
  },
  {
    id: 'skill_upload_policy_file',
    name: '上传制度文件',
    description: '上传并解析制度。',
    required_inputs: [{ label: '制度文件' }],
    output_types: ['finding'],
    can_update_assets: false
  },
  {
    id: 'skill_no_policy_basis',
    name: '无制度依据识别',
    description: '兼容旧任务，不应展示。',
    required_inputs: [{ label: 'BPMN 流程' }],
    output_types: ['finding'],
    can_update_assets: false
  }
];

describe('SkillPanel', () => {
  it('renders exactly the three demo skills', () => {
    render(
      <SkillPanel
        skills={skills}
        context={{ policyIds: [], processIds: [] }}
        runningSkillId={null}
        onSkillRun={vi.fn()}
      />
    );

    expect(screen.getByText('多制度冲突检查')).toBeInTheDocument();
    expect(screen.getByText('制度与流程校验')).toBeInTheDocument();
    expect(screen.getByText('上传制度文件')).toBeInTheDocument();
    expect(screen.queryByText('无制度依据识别')).not.toBeInTheDocument();
    expect(screen.getAllByText('点选应用')).toHaveLength(3);
  });
});
