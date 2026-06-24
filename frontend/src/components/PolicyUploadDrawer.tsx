import { Alert, Button, Checkbox, Descriptions, Drawer, Input, Modal, Progress, Select, Space, Tag, Upload } from 'antd';
import { Download, UploadCloud } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import type { PolicyDocument, PolicyUploadAnalysis, TreeItem } from '../types';
import { ClauseTree } from './ClauseTree';

type Props = {
  open: boolean;
  policyTree: TreeItem[];
  onClose: () => void;
  onSaved: (policy: PolicyDocument) => void;
};

function categoryOptions(tree: TreeItem[]) {
  return tree.map((item) => ({ label: item.title, value: item.title }));
}

export function PolicyUploadDrawer({ open, policyTree, onClose, onSaved }: Props) {
  const [analysis, setAnalysis] = useState<PolicyUploadAnalysis>();
  const [category, setCategory] = useState<string>();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [forceConfirmed, setForceConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadStage, setUploadStage] = useState('');
  const [uploadFileName, setUploadFileName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const options = useMemo(() => categoryOptions(policyTree), [policyTree]);

  async function analyze(option: {
    file: unknown;
    onProgress?: (event: { percent: number }) => void;
    onSuccess?: (result: unknown) => void;
    onError?: (error: Error) => void;
  }) {
    const file = option.file as File;
    setLoading(true);
    setError(null);
    setAnalysis(undefined);
    setUploadFileName(file.name);
    setUploadStage('上传并解析文件');
    setUploadPercent(6);
    option.onProgress?.({ percent: 6 });
    let percent = 6;
    const timer = window.setInterval(() => {
      percent = Math.min(92, percent + Math.max(1, Math.round((92 - percent) * 0.12)));
      setUploadPercent(percent);
      setUploadStage(percent < 35 ? '上传并抽取文本' : percent < 70 ? '解析条款层级' : '调用模型分析适配性');
      option.onProgress?.({ percent });
    }, 700);
    try {
      const result = await api.analyzePolicyUpload(file);
      window.clearInterval(timer);
      setUploadStage('分析完成');
      setUploadPercent(100);
      option.onProgress?.({ percent: 100 });
      setAnalysis(result);
      setForceConfirmed(false);
      setCategory(result.metadata.category || options[0]?.value);
      option.onSuccess?.(result);
    } catch (err) {
      window.clearInterval(timer);
      const message = err instanceof Error ? err.message : '上传分析失败';
      setError(message);
      option.onError?.(err as Error);
    } finally {
      setLoading(false);
    }
  }

  async function doSave() {
    if (!analysis || !category) return;
    setLoading(true);
    setError(null);
    try {
      const saved = await api.savePolicyUpload(analysis.analysis_id, category, answers);
      onSaved(saved);
      setAnalysis(undefined);
      setAnswers({});
      setForceConfirmed(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setLoading(false);
    }
  }

  function save() {
    if (!analysis || !category) return;
    const match = analysis.version_match;
    const versionText =
      match?.decision === 'auto_version'
        ? `系统已高置信度匹配到《${match.policy_name}》，保存后会作为该制度的新版本并默认生效。`
        : match?.decision === 'needs_confirmation'
          ? '你已在确认项中说明保存方式。若作为已有制度新版本保存，保存后会默认生效。'
          : '保存后会作为当前制度管理中的生效版本。';
    Modal.confirm({
      title: '确认保存版本',
      content: `${versionText}系统不会自动重跑既有风险，既有风险只会在查看时提示“该风险基于历史版本”。`,
      okText: '确认保存',
      cancelText: '取消',
      onOk: doSave
    });
  }

  return (
    <Drawer title="上传制度文件" width={760} open={open} onClose={onClose}>
      <Space direction="vertical" size={16} className="full-width">
        <Upload.Dragger accept=".pdf,.txt,.md" customRequest={analyze} maxCount={1} showUploadList={false} disabled={loading}>
          <p><UploadCloud /></p>
          <p>点击或拖拽上传制度文件</p>
          <p className="upload-hint">当前支持 PDF、TXT、Markdown。上传后先分析，不会直接入库。</p>
        </Upload.Dragger>

        {error ? <Alert type="error" showIcon message="处理失败" description={error} /> : null}

        {loading ? (
          <div className="upload-progress">
            <Progress percent={uploadPercent} status={error ? 'exception' : 'active'} />
            <div className="upload-file-name">{uploadFileName}</div>
            <div className="upload-hint">{uploadStage}</div>
          </div>
        ) : null}

        {analysis ? (
          <>
            <Alert
              type={analysis.suitable ? (analysis.questions.length || analysis.suggestions.length ? 'warning' : 'success') : 'error'}
              showIcon
              message={
                analysis.suitable
                  ? analysis.questions.length || analysis.suggestions.length
                    ? '文件可进入入库流程，存在需确认或后续完善事项'
                    : '文件适合进入制度入库流程'
                  : '文件暂不适合入库'
              }
              description={
                analysis.suitable
                  ? '系统仅将明显非制度型、不可解析或缺少基本制度结构的文件拒绝入库。角色定义、术语定义、追责章节、引用文件状态等属于完善项，可确认后先入库。'
                  : analysis.reasons.length ? analysis.reasons.join('；') : '未发现可支持入库的制度型结构。'
              }
            />

            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="制度名称">{analysis.metadata.name || '待确认'}</Descriptions.Item>
              <Descriptions.Item label="编号">{analysis.metadata.code || '待确认'}</Descriptions.Item>
              <Descriptions.Item label="版本">{analysis.metadata.version || '待确认'}</Descriptions.Item>
              <Descriptions.Item label="生效日期">{analysis.metadata.effective_date || '待确认'}</Descriptions.Item>
              <Descriptions.Item label="建议分类">{analysis.metadata.category || '待确认'}</Descriptions.Item>
              <Descriptions.Item label="条款数">{analysis.clauses.length}</Descriptions.Item>
              <Descriptions.Item label="源文件">
                {analysis.source_file ? (
                  <Button
                    icon={<Download size={14} />}
                    size="small"
                    type="link"
                    onClick={() => void api.downloadUploadSource(analysis.analysis_id, analysis.source_file?.file_name || analysis.file_name)}
                  >
                    下载源文件
                  </Button>
                ) : (
                  '未保留'
                )}
              </Descriptions.Item>
            </Descriptions>

            {analysis.version_match && analysis.version_match.decision !== 'new_policy' ? (
              <Alert
                type={analysis.version_match.decision === 'auto_version' ? 'success' : 'warning'}
                showIcon
                message={analysis.version_match.decision === 'auto_version' ? '将作为已有制度的新版本保存' : '疑似已有制度的新版本，需确认'}
                description={
                  analysis.version_match.decision === 'auto_version'
                    ? `匹配制度：《${analysis.version_match.policy_name}》。判断依据：${analysis.version_match.reason}；置信度 ${Math.round(analysis.version_match.confidence * 100)}%。`
                    : `疑似制度：《${analysis.version_match.policy_name}》。判断依据：${analysis.version_match.reason}；置信度 ${Math.round(analysis.version_match.confidence * 100)}%。`
                }
              />
            ) : null}

            <div>
              <div className="field-label">保存到制度管理结构项</div>
              <Select
                className="full-width"
                options={options}
                value={category}
                onChange={setCategory}
                placeholder="请选择制度管理结构项"
              />
            </div>

            {analysis.questions.length ? (
              <div className="question-stack">
                <div className="field-label">需要补充确认的问题</div>
                {analysis.questions.map((question) => (
                  <Input
                    key={question}
                    addonBefore={question}
                    value={answers[question] ?? ''}
                    onChange={(event) => setAnswers((items) => ({ ...items, [question]: event.target.value }))}
                  />
                ))}
                <Alert
                  type="info"
                  showIcon
                  message="回答用途"
                  description="这些回答会在保存时作为入库确认记录提交；不会自动重新解析文件。需要重新判断时请重新上传分析。"
                />
              </div>
            ) : null}

            {analysis.professional_questions?.length ? (
              <Alert
                type="warning"
                showIcon
                message="专业知识库提示需确认"
                description={analysis.professional_questions.map((question) => `${question.question}${question.reason ? `（${question.reason}）` : ''}`).join('；')}
              />
            ) : null}

            {analysis.professional_references?.length ? (
              <Alert
                type="info"
                showIcon
                message="已参考专业知识库"
                description={analysis.professional_references.map((reference) => reference.title || reference.source).join('；')}
              />
            ) : null}

            {analysis.suggestions.length ? (
              <Alert type="info" showIcon message="修改建议" description={analysis.suggestions.join('；')} />
            ) : null}

            {analysis.suitable && (analysis.questions.length || analysis.suggestions.length) ? (
              <Checkbox checked={forceConfirmed} onChange={(event) => setForceConfirmed(event.target.checked)}>
                我确认以上问题属于可后续完善的细节，本次仍先保存到制度管理。
              </Checkbox>
            ) : null}

            <div>
              <div className="field-label">角色/组织候选</div>
              <Space wrap>
                {analysis.concepts.map((concept) => (
                  <Tag color="blue" key={`${concept.node_type}-${concept.name}`}>{concept.name} · {concept.node_type}</Tag>
                ))}
              </Space>
            </div>

            <div>
              <div className="field-label">条款分层预览</div>
              <ClauseTree clauses={analysis.clauses} />
            </div>

            <Button
              block
              type="primary"
              loading={loading}
              disabled={!analysis.suitable || !category || ((analysis.questions.length > 0 || analysis.suggestions.length > 0) && !forceConfirmed)}
              onClick={save}
            >
              确认保存到制度管理
            </Button>
          </>
        ) : null}
      </Space>
    </Drawer>
  );
}
