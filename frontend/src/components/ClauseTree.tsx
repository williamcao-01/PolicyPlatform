import { Tag, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { PolicyClause } from '../types';

type Props = {
  clauses: PolicyClause[];
  highlightTerms?: string[];
};

function highlightConcepts(text: string, terms: string[]) {
  const matched = terms.filter((term) => term && text.includes(term)).sort((a, b) => b.length - a.length);
  if (matched.length === 0) return text;
  const pattern = new RegExp(`(${matched.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
  return text.split(pattern).map((part, index) =>
    matched.includes(part) ? (
      <mark key={`${part}-${index}`} className="concept-highlight">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function levelLabel(clauseNo: string) {
  if (clauseNo.includes('(')) return '明细';
  const depth = clauseNo.split('.').length;
  if (depth === 1) return '一级';
  if (depth === 2) return '二级';
  if (depth === 3) return '三级';
  return `${depth}级`;
}

function buildClauseTree(clauses: PolicyClause[], terms: string[]): DataNode[] {
  const childrenByParent = new Map<string | null, PolicyClause[]>();
  clauses.forEach((clause) => {
    const parent = clause.parent_id ?? null;
    childrenByParent.set(parent, [...(childrenByParent.get(parent) ?? []), clause]);
  });
  childrenByParent.forEach((items) => items.sort((left, right) => left.order_index - right.order_index));

  function toNode(clause: PolicyClause): DataNode {
    const children = childrenByParent.get(clause.id) ?? [];
    return {
      key: clause.id,
      title: (
        <div className="clause-tree-title">
          <div className="clause-tree-heading">
            <Tag>{levelLabel(clause.clause_no)}</Tag>
            <strong>{highlightConcepts(`${clause.clause_no} ${clause.title}`, terms)}</strong>
          </div>
          <div className="clause-tree-content">{highlightConcepts(clause.content, terms)}</div>
        </div>
      ),
      children: children.map(toNode)
    };
  }

  return (childrenByParent.get(null) ?? []).map(toNode);
}

export function ClauseTree({ clauses, highlightTerms = [] }: Props) {
  return (
    <Tree
      className="clause-tree"
      selectable={false}
      defaultExpandAll
      treeData={buildClauseTree(clauses, highlightTerms)}
    />
  );
}
