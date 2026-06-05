import { Button, Descriptions, Drawer, List, Modal, Tabs, Tag } from 'antd';
import { Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import BpmnViewer from 'bpmn-js/lib/Viewer';
import type { PolicyDocument, ProcessDefinition, RoleInventory } from '../types';
import { ClauseTree } from './ClauseTree';

type Props = {
  policy?: PolicyDocument;
  process?: ProcessDefinition;
  roleInventory?: RoleInventory;
  open: boolean;
  onClose: () => void;
  onDeletePolicy: (policyId: string) => Promise<void>;
  onDeleteProcess: (processId: string) => Promise<void>;
};

function BpmnCanvas({ xml }: { xml: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!xml.includes('BPMNDiagram') || !xml.includes('BPMNPlane')) {
      setError('BPMN 文件缺少图形坐标信息，无法渲染为流程图。');
      return;
    }
    const viewer = new BpmnViewer({ container: containerRef.current });
    let active = true;
    async function render() {
      try {
        await viewer.importXML(xml);
        if (!active) return;
        const canvas = viewer.get('canvas') as { zoom: (mode: string) => void; getRootElement?: () => unknown };
        if (!canvas.getRootElement?.()) {
          throw new Error('BPMN 图形根节点缺失。');
        }
        canvas.zoom('fit-viewport');
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'BPMN 渲染失败');
      }
    }
    void render();
    return () => {
      active = false;
      viewer.destroy();
    };
  }, [xml]);

  return (
    <>
      <div ref={containerRef} className="bpmn-canvas" />
      {error ? <pre className="xml-fallback">{`${error}\n\n${xml}`}</pre> : null}
    </>
  );
}

export function AssetDetailDrawer({ policy, process, roleInventory, open, onClose, onDeletePolicy, onDeleteProcess }: Props) {
  const [deleting, setDeleting] = useState(false);
  const terms =
    roleInventory?.policy_roles
      .filter((role) => !policy || role.mentions.some((mention) => mention.asset_id === policy.id))
      .map((role) => role.name) ?? [];
  const policyTerms = policy ? terms : [];
  function confirmDelete() {
    const assetName = policy?.name ?? process?.asset.file_name;
    const assetType = policy ? '制度' : '审批流';
    Modal.confirm({
      title: `确认删除${assetType}`,
      content: `删除后将从左侧${assetType}管理中移除“${assetName}”。此操作不会自动关闭既有风险记录。`,
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        setDeleting(true);
        try {
          if (policy) await onDeletePolicy(policy.id);
          if (process) await onDeleteProcess(process.id);
        } finally {
          setDeleting(false);
        }
      }
    });
  }

  return (
    <Drawer
      title={policy ? `${policy.name} 原文` : process ? `${process.asset.file_name} 流程文件` : '资产详情'}
      width={720}
      open={open}
      onClose={onClose}
      footer={
        policy || process ? (
          <div className="drawer-footer-actions">
            <Button danger icon={<Trash2 size={15} />} loading={deleting} onClick={confirmDelete}>
              {policy ? '删除制度' : '删除审批流'}
            </Button>
          </div>
        ) : null
      }
    >
      {policy ? (
        <div className="detail-stack">
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="编号">{policy.code}</Descriptions.Item>
            <Descriptions.Item label="版本">{policy.version}</Descriptions.Item>
            <Descriptions.Item label="类别">{policy.category}</Descriptions.Item>
            <Descriptions.Item label="适用范围">{policy.org_scope}</Descriptions.Item>
            <Descriptions.Item label="状态">{policy.status}</Descriptions.Item>
            <Descriptions.Item label="生效日期">{policy.effective_date}</Descriptions.Item>
          </Descriptions>
          <div>
            <div className="detail-header">
              <span>结构化条款</span>
              <span className="concept-tags">
                {policyTerms.map((term) => (
                  <Tag color="blue" key={term}>{term}</Tag>
                ))}
              </span>
            </div>
            <ClauseTree clauses={policy.clauses} highlightTerms={terms} />
          </div>
        </div>
      ) : null}

      {process ? (
        <Tabs
          items={[
            {
              key: 'diagram',
              label: 'BPMN 图',
              children: <BpmnCanvas xml={process.asset.bpmn_xml} />
            },
            {
              key: 'nodes',
              label: '结构化节点',
              children: (
                <List
                  dataSource={process.nodes}
                  renderItem={(node) => (
                    <List.Item>
                      <List.Item.Meta
                        title={`${node.order_index}. ${node.name}`}
                        description={
                          <>
                            <Tag>{node.role}</Tag>
                            <Tag color="blue">{node.action}</Tag>
                            {node.condition ? <Tag color="orange">{node.condition}</Tag> : null}
                          </>
                        }
                      />
                    </List.Item>
                  )}
                />
              )
            },
            {
              key: 'xml',
              label: '源文件 XML',
              children: <pre className="xml-fallback">{process.asset.bpmn_xml}</pre>
            }
          ]}
        />
      ) : null}
    </Drawer>
  );
}
