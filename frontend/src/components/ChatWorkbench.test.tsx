import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatWorkbench } from './ChatWorkbench';
import type { SkillDefinition, SkillRunResult } from '../types';

const skills: SkillDefinition[] = [
  {
    id: 'skill_policy_process_check',
    name: '制度与流程校验',
    description: '检查制度与流程。',
    required_inputs: [],
    output_types: ['finding'],
    can_update_assets: true
  }
];

describe('ChatWorkbench', () => {
  it('starts with an empty chat surface', () => {
    render(
      <ChatWorkbench
        skills={skills}
        context={{ policyIds: ['policy_purchase'], processIds: ['process_purchase'] }}
        assetLabelMap={{ policy_purchase: '采购制度', process_purchase: '采购流程.bpmn' }}
        results={[]}
        runningSkillId={null}
        error={null}
        onSkillRun={vi.fn(async () => undefined)}
        onExportFindingsExcel={vi.fn(async () => undefined)}
      />
    );

    expect(screen.queryByText('制度治理助手')).not.toBeInTheDocument();
    expect(screen.queryByText('制度与流程校验')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入补充说明，或从右侧点选任务')).toBeInTheDocument();
  });

  it('continues the latest skill when user answers clarification questions', async () => {
    const onSkillRun = vi.fn(async () => undefined);
    const result: SkillRunResult = {
      id: 'run_1',
      skill_id: 'skill_policy_process_check',
      status: 'completed',
      summary: '制度与流程校验完成，需确认问题 1 个。',
      execution_steps: ['读取输入资产', '生成待确认项'],
      final_answer: '需要确认该流程是否适用。',
      findings: [],
      hook_event_ids: [],
      professional_references: [],
      questions: [
        {
          id: 'q1',
          question: '该流程是否适用于基差采购？',
          reason: '适用范围会影响判断。',
          blocking: true,
          source: 'llm'
        }
      ]
    };

    render(
      <ChatWorkbench
        skills={skills}
        context={{ policyIds: ['policy_purchase'], processIds: ['process_purchase'] }}
        assetLabelMap={{ policy_purchase: '采购制度', process_purchase: '采购流程.bpmn' }}
        results={[result]}
        runningSkillId={null}
        error={null}
        onSkillRun={onSkillRun}
        onExportFindingsExcel={vi.fn(async () => undefined)}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('回复待确认项，系统会继续执行当前任务'), {
      target: { value: '适用，同一条采购申请流程覆盖基差采购。' }
    });
    const sendButtons = screen.getAllByRole('button', { name: '发送' });
    fireEvent.click(sendButtons[sendButtons.length - 1]);

    expect(await screen.findByText(/已收到/)).toBeInTheDocument();
    expect(screen.queryByText('等待确认')).not.toBeInTheDocument();
    expect(onSkillRun).toHaveBeenCalledWith('skill_policy_process_check', {
      '该流程是否适用于基差采购？': '适用，同一条采购申请流程覆盖基差采购。'
    });
  });

  it('exports excel instead of treating the request as a clarification answer', async () => {
    const onSkillRun = vi.fn(async () => undefined);
    const onExportFindingsExcel = vi.fn(async () => undefined);
    const result: SkillRunResult = {
      id: 'run_1',
      skill_id: 'skill_policy_process_check',
      status: 'completed',
      summary: '需要确认。',
      execution_steps: [],
      final_answer: '需要确认。',
      findings: [],
      hook_event_ids: [],
      professional_references: [],
      questions: [
        {
          id: 'q1',
          question: '该流程是否适用？',
          reason: '需要确认。',
          blocking: true,
          source: 'llm'
        }
      ]
    };

    render(
      <ChatWorkbench
        skills={skills}
        context={{ policyIds: ['policy_purchase'], processIds: ['process_purchase'] }}
        assetLabelMap={{ policy_purchase: '采购制度', process_purchase: '采购流程.bpmn' }}
        results={[result]}
        runningSkillId={null}
        error={null}
        onSkillRun={onSkillRun}
        onExportFindingsExcel={onExportFindingsExcel}
      />
    );

    const inputs = screen.getAllByPlaceholderText('回复待确认项，系统会继续执行当前任务');
    fireEvent.change(inputs[inputs.length - 1], {
      target: { value: '以上问题下载个excel给我' }
    });
    const sendButtons = screen.getAllByRole('button', { name: '发送' });
    fireEvent.click(sendButtons[sendButtons.length - 1]);

    expect(await screen.findByText(/当前对话没有可导出的结果/)).toBeInTheDocument();
    expect(onExportFindingsExcel).toHaveBeenCalledOnce();
    expect(onSkillRun).not.toHaveBeenCalled();
  });
});
