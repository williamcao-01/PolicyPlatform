import { Card } from 'antd';
import type { SkillRunResult } from '../../types';

export function SkillResultCard({ result }: { result: SkillRunResult }) {
  return (
    <Card className="skill-result-card" size="small">
      <details className="thinking-panel">
        <summary>思考与执行过程</summary>
        <ol>
          {(result.execution_steps.length ? result.execution_steps : [result.summary]).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </details>

      {result.professional_references.length ? (
        <div className="reference-panel">
          <div className="section-label">引用依据</div>
          <p className="reference-impact">{referenceImpact(result)}</p>
          <ul className="reference-list">
            {result.professional_references.slice(0, 6).map((reference) => (
              <li className="reference-item" key={`${reference.source}-${reference.title}`}>
                <strong>{reference.title || reference.source}</strong>
                <span>{reference.source}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="final-response">
        <div className="section-label">最终回复</div>
        <p>{result.final_answer || result.summary}</p>

        {result.questions.length ? (
          <div className="clarification-list">
            {result.questions.map((question) => (
              <div className="clarification-item" key={question.id}>
                <strong>{question.question}</strong>
                {question.reason ? <span>{question.reason}</span> : null}
              </div>
            ))}
          </div>
        ) : null}

        {result.findings.length && !result.questions.length ? (
          <div className="risk-stack">
            <div className="risk-count">共发现 {result.findings.length} 个风险点。</div>
            {result.findings.map((finding, index) => (
              <article className="risk-card" key={finding.id}>
                <div className="risk-heading">
                  <strong>
                    {index + 1}. {finding.title}
                  </strong>
                  <span>{finding.verification_status === 'uncertain' ? '不确定' : finding.severity}</span>
                </div>
                {finding.verification_status === 'uncertain' ? (
                  <div className="verification-warning">
                    <strong>二次验证结论：不确定</strong>
                    <p>{finding.verification_note || '当前证据不足以确认该风险结论，需要补充制度、流程或业务事实后再判断。'}</p>
                  </div>
                ) : (
                  <div className="verification-note">二次验证：已确认当前证据能够支撑该风险结论。</div>
                )}
                {finding.based_on_historical_version ? (
                  <div className="verification-warning">
                    <strong>该风险基于历史版本</strong>
                    <p>相关制度或审批流已产生新版本，系统不会自动重跑该风险。需要当前版本结论时，请重新执行任务。</p>
                  </div>
                ) : null}
                <div className="risk-section">
                  <span>风险描述</span>
                  <p className="risk-detail">{finding.description}</p>
                </div>
                {finding.evidence.length ? (
                  <div className="risk-evidence-list" aria-label="制度引用">
                    <span>原文依据</span>
                    {finding.evidence.map((evidence) => (
                      <div className="risk-evidence" key={evidence.id}>
                        <span>{evidence.label}</span>
                        <em>{evidence.quote}</em>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="risk-assumption">
                  <span>判断假设</span>
                  <p>{finding.assumption || '基于当前所选制度条款和 BPMN 节点作为本次核验的有效证据范围。'}</p>
                </div>
                {finding.suggestion ? (
                  <div className="risk-section">
                    <span>优化建议</span>
                    <p className="risk-suggestion">{finding.suggestion}</p>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </Card>
  );
}

function referenceImpact(result: SkillRunResult) {
  const directImpact = result.professional_references.find((reference) => reference.impact)?.impact;
  if (directImpact) return directImpact;
  return '这些依据用于补充专业判断框架、术语边界和治理建议；最终风险仍以本次选择的制度条款和 BPMN 节点作为证据。';
}
