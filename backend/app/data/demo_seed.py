from __future__ import annotations

from app.models import (
    Evidence,
    Finding,
    KnowledgeEdge,
    KnowledgeNode,
    PolicyClause,
    PolicyDocument,
    ProcessAsset,
    ProcessDefinition,
    ProcessNode,
    PolicyVersion,
    ProcessVersion,
)


def _bpmn_from_nodes(process_id: str, process_name: str, nodes: list[ProcessNode]) -> str:
    task_xml = "\n".join(
        f'    <bpmn:userTask id="{node.bpmn_element_id}" name="{node.name}" />' for node in nodes
    )
    flows: list[tuple[str, str, str]] = []
    previous = "start"
    for node in nodes:
        flows.append((f"flow_{previous}_{node.bpmn_element_id}", previous, node.bpmn_element_id))
        previous = node.bpmn_element_id
    flows.append((f"flow_{previous}_end", previous, "end"))
    flow_xml = "\n".join(
        f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{source}" targetRef="{target}" />'
        for flow_id, source, target in flows
    )

    shapes = [
        '      <bpmndi:BPMNShape id="shape_start" bpmnElement="start"><dc:Bounds x="80" y="130" width="36" height="36" /></bpmndi:BPMNShape>'
    ]
    element_xy: dict[str, tuple[int, int]] = {"start": (80, 148)}
    x = 160
    for index, node in enumerate(nodes):
        y = 98 if index % 2 == 0 else 218
        shapes.append(
            f'      <bpmndi:BPMNShape id="shape_{node.bpmn_element_id}" bpmnElement="{node.bpmn_element_id}"><dc:Bounds x="{x}" y="{y}" width="138" height="72" /></bpmndi:BPMNShape>'
        )
        element_xy[node.bpmn_element_id] = (x, y + 36)
        x += 170
    shapes.append(
        f'      <bpmndi:BPMNShape id="shape_end" bpmnElement="end"><dc:Bounds x="{x}" y="130" width="36" height="36" /></bpmndi:BPMNShape>'
    )
    element_xy["end"] = (x, 148)
    edges = []
    for flow_id, source, target in flows:
        sx, sy = element_xy[source]
        tx, ty = element_xy[target]
        source_width = 36 if source == "start" else 138
        edges.append(
            f'      <bpmndi:BPMNEdge id="edge_{flow_id}" bpmnElement="{flow_id}"><di:waypoint x="{sx + source_width}" y="{sy}" /><di:waypoint x="{tx}" y="{ty}" /></bpmndi:BPMNEdge>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="defs_{process_id}" targetNamespace="http://demo.policy.ai/{process_id}">
  <bpmn:process id="{process_id}" name="{process_name}" isExecutable="false">
    <bpmn:startEvent id="start" name="开始" />
{task_xml}
    <bpmn:endEvent id="end" name="结束" />
{flow_xml}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="diagram_{process_id}">
    <bpmndi:BPMNPlane id="plane_{process_id}" bpmnElement="{process_id}">
{chr(10).join(shapes)}
{chr(10).join(edges)}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


def _pc(policy_id: str, suffix: str, clause_no: str, title: str, content: str, order_index: int, parent_id: str | None = None) -> PolicyClause:
    return PolicyClause(
        id=f"clause_{suffix}",
        policy_id=policy_id,
        clause_no=clause_no,
        title=title,
        content=content,
        parent_id=parent_id,
        order_index=order_index,
    )


def _node(process_id: str, suffix: str, element_id: str, name: str, role: str, action: str, order_index: int, condition: str | None = None) -> ProcessNode:
    return ProcessNode(
        id=f"node_{suffix}",
        process_id=process_id,
        bpmn_element_id=element_id,
        name=name,
        role=role,
        action=action,
        condition=condition,
        order_index=order_index,
    )


def _process(process_id: str, name: str, code: str, domain: str, scope: str, file_name: str, nodes: list[ProcessNode]) -> ProcessDefinition:
    return ProcessDefinition(
        id=process_id,
        name=name,
        code=code,
        business_domain=domain,
        org_scope=scope,
        status="enabled",
        nodes=nodes,
        asset=ProcessAsset(
            id=f"asset_{process_id}_bpmn",
            process_id=process_id,
            file_name=file_name,
            bpmn_xml=_bpmn_from_nodes(process_id, name, nodes),
        ),
    )


def build_demo_dataset() -> dict:
    policies = [
        PolicyDocument(
            id="policy_purchase_platform",
            name="集团采购授权与供应商准入管理办法",
            code="YN-CG-1.0.0",
            version="B/1",
            category="招采管理",
            org_scope="平台公司、事业部及下属企业",
            status="effective",
            effective_date="2025-09-01",
            clauses=[
                _pc("policy_purchase_platform", "platform_1", "1", "目的", "为统一平台及下属企业采购授权、供应商准入、合同签署和执行留痕要求，建立采购事项从需求、寻源、定价、审批、合同、验收到归档的全过程管控机制。", 1),
                _pc("policy_purchase_platform", "platform_2_1", "2.1", "适用范围", "本办法适用于平台公司及下属企业的工程、原料、设备、服务和信息化采购。涉及期货、基差、战略物资或单一来源采购的，应同时执行专项制度；专项制度与本办法不一致时，按权限更高、控制更严原则执行。", 2),
                _pc("policy_purchase_platform", "platform_3_1", "3.1", "采购中心职责", "采购中心负责采购策略、供应商准入、寻源组织、价格谈判、采购订单和供应商绩效管理；采购中心不得兼任合规审查或合同法务审查职责。", 3),
                _pc("policy_purchase_platform", "platform_3_2", "3.2", "风控合规部职责", "风控合规部负责对战略物资、单一来源、关联交易、异常价格偏离和金额超过50万元的采购事项进行风控复核，并出具复核意见。", 4),
                _pc("policy_purchase_platform", "platform_3_3", "3.3", "法务部职责", "法务部负责采购合同文本、非标条款、违约责任、用印合规和授权链条审查；未经法务部审查的非标合同不得进入用印环节。", 5),
                _pc("policy_purchase_platform", "platform_4_1", "4.1", "采购权限矩阵", "单笔采购金额超过30万元的，应由采购部门负责人审核；超过80万元的，提交平台总经理审批；超过200万元或涉及战略物资的，提交招采委员会审议后由平台总经理审批。", 6),
                _pc("policy_purchase_platform", "platform_4_2", "4.2", "特殊事项控制", "单一来源采购、紧急采购、供应商首次准入、价格偏离市场均价超过5%的采购事项，应增加风控复核和法务审查，形成《采购特殊事项说明》。", 7),
                _pc("policy_purchase_platform", "platform_5_1", "5.1", "供应商准入", "供应商首次准入由采购中心发起，供应商管理办公室完成资质核验、黑名单筛查和主数据建档；涉及生产厂家直采的，应补充质量管理部现场评估意见。", 8),
                _pc("policy_purchase_platform", "platform_6_1", "6.1", "过程记录", "采购事项应保留需求申请、询比价记录、供应商准入记录、审批记录、合同审查记录、验收记录和归档清单，作为制度执行证据。", 9),
            ],
        ),
        PolicyDocument(
            id="policy_purchase",
            name="饲料原料基差采购业务工作细则",
            code="YN-CZ-6.3.5",
            version="A/O",
            category="招采管理",
            org_scope="平台采购中心、饲料产品部及下属饲料厂",
            status="effective",
            effective_date="2025-11-27",
            clauses=[
                _pc("policy_purchase", "basis_1", "1", "目的", "为规范豆粕、玉米、菜粕等饲料原料基差采购业务，控制期现价格波动、供应保障和点价执行风险，根据《集团采购授权与供应商准入管理办法》制定本细则。", 1),
                _pc("policy_purchase", "basis_2", "2", "适用范围", "本细则适用于平台采购中心统一组织、下属饲料厂提出需求、采用基差合同或点价方式采购的饲料原料。现货普通采购、设备采购和服务采购不适用本细则。", 2),
                _pc("policy_purchase", "basis_3_1", "3.1", "基差定义", "基差指现货价格与期货价格的差值，基差采购合同应明确基差、期货合约、点价窗口、提货周期和结算方式。", 3),
                _pc("policy_purchase", "basis_3_2", "3.2", "点价定义", "点价指采购方在合同约定窗口内选择期货盘面价格作为计价基准，并与供应商确认最终采购价。", 4),
                _pc("policy_purchase", "basis_4_1", "4.1", "采购中心职责", "采购中心负责基差市场研判、采购策略制定、供应商沟通、基差谈判、点价指令管理、点价确认和采购台账维护。", 5),
                _pc("policy_purchase", "basis_4_2", "4.2", "饲料产品部职责", "饲料产品部负责汇总各饲料厂需求、核对库存和生产计划，复核点价申请中的需求数量、提货窗口和替代料风险。", 6),
                _pc("policy_purchase", "basis_4_3", "4.3", "饲料原料采购决策小组职责", "饲料原料采购决策小组负责审议月度基差采购策略、单一来源采购理由、目标价区间和点价止损方案；会议纪要应上传供应链系统。", 7),
                _pc("policy_purchase", "basis_5_1", "5.1", "供应商分类", "采购中心应区分生产厂家、贸易商、关联供应商和临时供应商。生产厂家直采可采用微信、短信、传真等方式询价，但须形成《基差报价记录表》。", 8),
                _pc("policy_purchase", "basis_6_1", "6.1", "采购策略制定", "采购中心结合宏观经济、期货盘面、原料供需和库存安全量制定基差采购策略，提交饲料原料采购决策小组审议后方可寻源。", 9),
                _pc("policy_purchase", "basis_6_2_1", "6.2.1", "寻源前置条件", "寻源前，采购岗须核验供应商准入状态、生产厂家资质、历史履约记录和黑名单信息；临时供应商不得直接进入点价环节。", 10),
                _pc("policy_purchase", "basis_6_2_2", "6.2.2", "寻源执行", "生产厂家场景下，采购中心采购岗可通过微信、短信、邮件等渠道向供应商征询报价，并统一整理形成《基差报价记录表》上传供应链系统。", 11),
                _pc("policy_purchase", "basis_6_3", "6.3", "评审谈判和中选", "确认中选前，采购中心采购岗应将中选意向、报价记录和供应保障说明提交饲料原料采购决策小组确认；下属企业采购岗完成供应链系统线上审批/备案工作。", 12),
                _pc("policy_purchase", "basis_7_1_1", "7.1.1", "点价申请审批", "采购中心制定点价策略，明确目标价格区间、建议点价窗口、止损线和风险控制措施，提交《点价申请单》由饲料原料采购决策小组决策。单笔基差采购金额超过30万元的，应由采购部门负责人审核后提交平台总经理审批；涉及战略物资、关联供应商或单笔金额超过50万元的采购事项，应增加风控复核节点。", 13),
                _pc("policy_purchase", "basis_7_1_2", "7.1.2", "法务与合同审查", "基差合同金额超过30万元、采用非标合同文本、涉及作价协议或价格追补条款的，应在用印前提交法务部审查。", 14),
                _pc("policy_purchase", "basis_7_2_1", "7.2.1", "点价指令下达", "点价申请获批后，采购中心采购岗可通过供应商官方交易系统、邮件或传真件发出点价指令；口头或微信指令应在一个工作日内补录系统。", 15),
                _pc("policy_purchase", "basis_7_2_2", "7.2.2", "点价确认", "当期货盘面触发点价指令且与供应商确认成交后，下属企业通过用印审批流程提交《点价确认单》或《作价协议》盖章申请，并关联合同编号、生成采购订单。", 16),
                _pc("policy_purchase", "basis_7_3", "7.3", "归档管理", "采购中心应将基差合同、点价申请单、点价确认单、报价记录、审批记录、风控复核意见和法务审查意见长期归档。", 17),
                _pc("policy_purchase", "basis_8_1", "8.1", "盘面上行应急", "点价挂单未成交且盘面突破目标价位上限时，采购中心应报告采购中心原料组组长和饲料产品部负责人，重新制定点价策略并提交审批。", 18),
                _pc("policy_purchase", "basis_8_2", "8.2", "盘面下行应急", "点价挂单未成交且盘面跌破目标价位下限时，采购中心应撤单并报告采购中心原料组组长，重新评估采购时点和库存保障。", 19),
            ],
        ),
        PolicyDocument(
            id="policy_sub_purchase",
            name="子公司采购实施细则",
            code="ZCG-2024-002",
            version="2024.1",
            category="采购",
            org_scope="各子公司",
            status="effective",
            effective_date="2024-03-01",
            clauses=[
                _pc("policy_sub_purchase", "sub_purchase_1_1", "1.1", "适用范围", "本细则适用于各子公司自行组织的原料、辅料、备品备件、维修服务和零星工程采购。平台统采、基差采购和战略物资采购按照平台专项制度执行。", 1),
                _pc("policy_sub_purchase", "sub_purchase_2_1", "第二条第一款", "子公司采购权限", "单笔采购金额超过50万元的，由子公司总经理审批；超过100万元的，报平台采购部备案。", 2),
                _pc("policy_sub_purchase", "sub_purchase_2_2", "第二条第二款", "紧急采购", "紧急抢修、停产风险或保供采购可由子公司总经理先行口头批准，采购实施部门应在两个工作日内补齐审批记录和合同用印资料。", 3),
                _pc("policy_sub_purchase", "sub_purchase_3_1", "3.1", "供应商选择", "子公司采购实施部门可从合格供应商名录中选择供应商；新供应商准入需提交采购中心复核。", 4),
                _pc("policy_sub_purchase", "sub_purchase_4_1", "4.1", "归档要求", "采购实施部门应保存采购申请、比价记录、审批记录、合同和验收单，子公司财务部按月抽查。", 5),
            ],
        ),
        PolicyDocument(
            id="policy_contract",
            name="合同及用印管理办法",
            code="YN-FW-2.1.0",
            version="C/0",
            category="合同法务",
            org_scope="平台及下属企业",
            status="effective",
            effective_date="2025-07-15",
            clauses=[
                _pc("policy_contract", "contract_1", "1", "目的", "为规范合同订立、审查、授权签署、用印和归档，防范合同法律风险和印章管理风险，制定本办法。", 1),
                _pc("policy_contract", "contract_3_1", "3.1", "合同发起", "业务经办部门应在合同发起时上传采购审批记录、供应商信息、合同文本、报价记录和履约计划。", 2),
                _pc("policy_contract", "contract_3_2", "3.2", "法务审查", "合同金额超过30万元、使用非标文本、涉及违约责任调整、关联供应商或跨期作价的，应提交法务部审查。", 3),
                _pc("policy_contract", "contract_3_3", "3.3", "财务复核", "合同金额超过100万元、付款条件超出标准账期或涉及预付款的，应由财务运营部复核资金计划和税务风险。", 4),
                _pc("policy_contract", "contract_3_4", "3.4", "合规审查", "关联交易、利益冲突、单一来源和异常价格偏离事项，应由风控合规部进行合规审查后方可用印。", 5),
                _pc("policy_contract", "contract_4_1", "4.1", "用印控制", "印章管理员应核验审批链、法务审查意见、授权签署人和合同附件完整性；缺少任一材料不得用印。", 6),
                _pc("policy_contract", "contract_5_1", "5.1", "归档", "用印完成后，经办部门应在五个工作日内提交合同正本扫描件、审批记录、用印记录和履约关键节点，法务部建立合同台账。", 7),
            ],
        ),
        PolicyDocument(
            id="policy_supplier",
            name="供应商准入与绩效评价办法",
            code="YN-GY-3.2.0",
            version="A/2",
            category="供应商管理",
            org_scope="平台及下属企业",
            status="effective",
            effective_date="2025-05-20",
            clauses=[
                _pc("policy_supplier", "supplier_1", "1", "目的", "为规范供应商准入、分级、绩效评价、黑名单和退出机制，保障采购质量、交付和合规要求，制定本办法。", 1),
                _pc("policy_supplier", "supplier_2_1", "2.1", "准入申请", "供应商准入由采购中心或业务需求部门发起，供应商管理办公室负责资质资料完整性审核和主数据建档。", 2),
                _pc("policy_supplier", "supplier_2_2", "2.2", "质量评估", "涉及生产厂家、饲料添加剂、关键原料或质量安全风险的供应商，应由质量管理部完成现场或远程质量评估。", 3),
                _pc("policy_supplier", "supplier_2_3", "2.3", "合规筛查", "新供应商应通过黑名单、关联关系、诉讼和重大舆情筛查；关联供应商、临时供应商和单一来源供应商应提交风控合规部复核。", 4),
                _pc("policy_supplier", "supplier_3_1", "3.1", "绩效评价", "采购中心每季度组织供应商绩效评价，评价维度包括交付、质量、价格、服务、合规和异常处理。", 5),
                _pc("policy_supplier", "supplier_4_1", "4.1", "退出机制", "连续两次绩效不合格、重大质量事故、商业贿赂或提供虚假材料的供应商，应纳入限制或退出名录。", 6),
            ],
        ),
        PolicyDocument(
            id="policy_recruit",
            name="招聘录用管理办法",
            code="HR-2024-001",
            version="2024.1",
            category="人力",
            org_scope="平台及子公司",
            status="effective",
            effective_date="2024-02-01",
            clauses=[
                _pc("policy_recruit", "recruit_1", "1", "目的", "为规范岗位编制、招聘需求、面试录用、背调和入职手续，明确招聘录用审批责任，制定本办法。", 1),
                _pc("policy_recruit", "recruit_2_1", "2.1", "招聘需求", "用人部门负责人根据年度编制和业务计划提出招聘需求，人力资源部复核编制余额、岗位等级和预算。", 2),
                _pc("policy_recruit", "recruit_3_1", "3.1", "面试评价", "用人部门负责人、人力资源负责人和业务分管领导共同确认关键岗位候选人的面试评价。", 3),
                _pc("policy_recruit", "recruit_4_1", "第四条第一款", "录用审批", "招聘录用应经用人部门负责人、人力资源负责人审核，并由分管领导审批。关键岗位、经理级及以上岗位应补充背景调查报告。", 4),
                _pc("policy_recruit", "recruit_4_2", "第四条第二款", "入职材料", "人力资源专员应在入职前收集身份证明、学历证明、离职证明、背调记录和录用审批记录。", 5),
                _pc("policy_recruit", "recruit_5_1", "5.1", "例外录用", "超编制、薪酬超预算或未完成背景调查的录用事项，应提交人力资源负责人和业务分管领导共同确认后方可发放录用通知。", 6),
            ],
        ),
        PolicyDocument(
            id="policy_salary",
            name="薪酬定级管理指引",
            code="HR-2024-002",
            version="2024.1",
            category="人力",
            org_scope="平台本部",
            status="effective",
            effective_date="2024-02-15",
            clauses=[
                _pc("policy_salary", "salary_2_1", "第二条第一款", "薪酬定级范围", "薪酬定级适用于平台本部正式员工，子公司参照执行但需另行制定细则。", 1),
                _pc("policy_salary", "salary_3_1", "3.1", "定级依据", "薪酬定级应以岗位职级、任职资格、市场薪酬区间、内部公平性和预算额度为依据。", 2),
                _pc("policy_salary", "salary_3_2", "3.2", "审批要求", "平台本部员工薪酬定级由人力资源负责人审核、业务分管领导审批；超预算或破格定级需提交薪酬委员会审议。", 3),
                _pc("policy_salary", "salary_4_1", "4.1", "记录要求", "薪酬定级表、审批意见和预算校验记录应归入员工薪酬档案，未经授权不得在招聘流程中公开流转。", 4),
            ],
        ),
        PolicyDocument(
            id="policy_institution_governance",
            name="制度建设与管理办法",
            code="YN-ZD-1.0.0",
            version="D/0",
            category="制度管理",
            org_scope="平台公司、事业部及下属企业",
            status="effective",
            effective_date="2026-01-01",
            clauses=[
                _pc("policy_institution_governance", "inst_gov_1", "1", "目的", "为规范制度立项、起草、会签、审批、发布、培训、执行、复核、修订和废止全过程管理，建立制度全生命周期闭环和版本可追溯机制。", 1),
                _pc("policy_institution_governance", "inst_gov_2_1", "2.1", "制度分级", "制度分为基本制度、管理办法、实施细则、操作指引四级。上位制度与下位制度不一致时，以上位制度为准；专项制度规定更严的，按更严要求执行。", 2),
                _pc("policy_institution_governance", "inst_gov_2_2", "2.2", "适用范围", "本办法适用于平台公司、事业部及下属企业新建、修订、解释、废止和执行评价的所有制度文件。流程图、表单模板、操作手册作为制度配套文件纳入关联管理。", 3),
                _pc("policy_institution_governance", "inst_gov_3_1", "3.1", "制度管理办公室职责", "制度管理办公室负责制度目录、编号规则、版本台账、发布归档、年度复核计划和制度知识库维护，并对制度冲突和版本失效风险进行跟踪。", 4),
                _pc("policy_institution_governance", "inst_gov_3_2", "3.2", "业务归口部门职责", "业务归口部门负责提出制度立项申请、组织起草和业务评审，说明制度适用范围、流程影响、角色职责和历史制度替代关系。", 5),
                _pc("policy_institution_governance", "inst_gov_3_3", "3.3", "法务部职责", "法务部负责审查制度中的授权边界、合同法律风险、外部法规引用、责任追究和争议处理条款。涉及合同、用印、劳动关系、知识产权和数据合规的制度必须法务会签。", 6),
                _pc("policy_institution_governance", "inst_gov_3_4", "3.4", "风控合规部职责", "风控合规部负责审查制度中的关键控制点、职责分离、例外授权、监管合规和内控证据要求。涉及采购、资金、销售、数据、关联交易和重大授权的制度必须风控合规会签。", 7),
                _pc("policy_institution_governance", "inst_gov_4_1", "4.1", "立项要求", "新建或重大修订制度应由业务归口部门提交《制度立项申请单》，说明制度依据、拟解决问题、影响流程、影响岗位、替代或废止文件和预计生效时间。", 8),
                _pc("policy_institution_governance", "inst_gov_4_2", "4.2", "制度起草", "制度起草应采用统一模板，至少包括目的、适用范围、术语定义、职责分工、管理要求、流程接口、监督检查、违规处理、生效日期和附件清单。", 9),
                _pc("policy_institution_governance", "inst_gov_5_1", "5.1", "会签规则", "跨部门制度应由相关部门会签；涉及财务影响的由财务运营部会签，涉及系统权限或数据处理的由信息技术部会签，涉及员工权益的由人力资源部会签。", 10),
                _pc("policy_institution_governance", "inst_gov_5_2", "5.2", "审批权限", "管理办法由业务分管领导审核、平台总经理审批；基本制度由总经理办公会审议后发布；实施细则和操作指引由业务归口部门负责人审批后报制度管理办公室备案。", 11),
                _pc("policy_institution_governance", "inst_gov_6_1", "6.1", "版本编号", "制度版本号采用“主版本/修订号”规则。重大修订提升主版本，文字修订或附件更新提升修订号。若正文未写明版本号，制度管理办公室应按台账自动生成版本号并记录生成依据。", 12),
                _pc("policy_institution_governance", "inst_gov_6_2", "6.2", "默认生效", "新版本制度经审批发布后默认为当前生效版本；历史版本自动转为失效或归档状态。系统不得自动重跑历史风险结论，但应在风险清单中提示“该风险基于历史版本”。", 13),
                _pc("policy_institution_governance", "inst_gov_6_3", "6.3", "发布与培训", "制度发布应同步更新制度树、版本台账、流程关联关系和角色清单。涉及一线执行岗位或审批流变更的，应在生效前完成宣贯培训并留存培训记录。", 14),
                _pc("policy_institution_governance", "inst_gov_7_1", "7.1", "年度复核", "制度管理办公室每年组织制度年度复核，业务归口部门应评估制度有效性、流程匹配性、执行问题、外部法规变化和废止建议。逾期未复核的制度标记为待复核。", 15),
                _pc("policy_institution_governance", "inst_gov_7_2", "7.2", "冲突处理", "发现制度之间存在适用范围、审批权限、金额阈值、角色职责或生效版本冲突的，制度管理办公室应发起冲突处理单，由相关业务归口部门确认优先级和修订计划。", 16),
                _pc("policy_institution_governance", "inst_gov_8_1", "8.1", "废止管理", "制度废止应说明废止原因、替代文件、影响流程和过渡安排，经业务分管领导审核、制度管理办公室复核、平台总经理审批后发布废止通知。", 17),
            ],
        ),
        PolicyDocument(
            id="policy_institution_publish",
            name="制度发布与版本控制实施细则",
            code="YN-ZD-1.1.0",
            version="B/2",
            category="制度管理",
            org_scope="平台制度管理办公室、各业务归口部门",
            status="effective",
            effective_date="2026-02-01",
            clauses=[
                _pc("policy_institution_publish", "inst_pub_1", "1", "目的", "为细化制度发布、编号、版本、源文件留存、公告、培训和历史版本追溯要求，制定本细则。", 1),
                _pc("policy_institution_publish", "inst_pub_2_1", "2.1", "编号规则", "制度编号由公司简称、业务域代码、制度序号和版本序列组成。制度管理办公室负责编号分配，业务归口部门不得自行编号。", 2),
                _pc("policy_institution_publish", "inst_pub_2_2", "2.2", "源文件留存", "制度发布时必须保留最终审批稿、PDF版、正文解析结果、审批记录、会签意见和附件清单。源文件缺失的，不得标记为正式发布。", 3),
                _pc("policy_institution_publish", "inst_pub_3_1", "3.1", "生效时间", "制度发布后原则上在五个工作日后生效；制度正文明确即时生效或审批意见要求即时生效的，可在发布当日生效。", 4),
                _pc("policy_institution_publish", "inst_pub_3_2", "3.2", "版本切换", "新版本发布时，制度管理系统应将该版本设为默认生效版本，历史版本保留但不得作为新任务默认依据。已经形成的风险记录不自动关闭。", 5),
                _pc("policy_institution_publish", "inst_pub_3_3", "3.3", "低置信度匹配", "上传制度文件时，系统应基于制度名称、编号和主题相似度判断是否为已有制度的新版本。低置信度匹配必须由制度管理员人工确认后方可入库。", 6),
                _pc("policy_institution_publish", "inst_pub_4_1", "4.1", "发布公告", "发布公告应列明制度名称、编号、版本、生效日期、废止文件、主要变化、影响流程和联系人。", 7),
                _pc("policy_institution_publish", "inst_pub_4_2", "4.2", "培训要求", "涉及采购、资金、合同、人力、生产、安全和数据管理等关键业务的制度，应由业务归口部门在生效前完成培训；紧急发布制度可在生效后五个工作日内补训。", 8),
                _pc("policy_institution_publish", "inst_pub_5_1", "5.1", "历史版本引用", "历史版本仅用于审计追溯、历史问题复盘和争议处理。系统展示历史版本风险时，应提示“该风险基于历史版本”。", 9),
            ],
        ),
        PolicyDocument(
            id="policy_institution_review",
            name="制度年度复核与执行评价办法",
            code="YN-ZD-2.0.0",
            version="A/1",
            category="制度管理",
            org_scope="平台公司及下属企业",
            status="effective",
            effective_date="2026-03-01",
            clauses=[
                _pc("policy_institution_review", "inst_rev_1", "1", "目的", "为评价制度执行有效性、识别制度冲突和流程偏差、推动制度持续优化，制定本办法。", 1),
                _pc("policy_institution_review", "inst_rev_2_1", "2.1", "复核对象", "纳入制度目录的现行有效制度、试行制度、配套流程图和关键表单均应参加年度复核。", 2),
                _pc("policy_institution_review", "inst_rev_2_2", "2.2", "复核维度", "年度复核至少覆盖制度适用性、审批权限、角色职责、流程匹配、执行证据、外部法规变化、系统配置和历史问题整改情况。", 3),
                _pc("policy_institution_review", "inst_rev_3_1", "3.1", "业务自评", "业务归口部门应对制度执行情况进行自评，说明执行偏差、例外审批、未按制度执行事项和拟修订建议。", 4),
                _pc("policy_institution_review", "inst_rev_3_2", "3.2", "制度管理办公室复核", "制度管理办公室负责汇总自评材料，检查制度目录、版本状态、流程关联、角色映射和知识库词汇是否一致。", 5),
                _pc("policy_institution_review", "inst_rev_3_3", "3.3", "风控抽查", "风控合规部应对采购、资金、合同、人力和数据管理等高风险制度开展抽查，并对发现问题形成整改清单。", 6),
                _pc("policy_institution_review", "inst_rev_4_1", "4.1", "整改闭环", "复核发现的问题应分为制度冲突、流程不一致、无制度依据、角色不一致、版本失效和执行证据缺失六类，明确责任部门、整改期限和复核人。", 7),
                _pc("policy_institution_review", "inst_rev_4_2", "4.2", "逾期处理", "整改逾期超过30日的，由制度管理办公室提交业务分管领导督办；重大风险逾期超过60日的，提交总经理办公会通报。", 8),
            ],
        ),
        PolicyDocument(
            id="policy_process_governance",
            name="审批流程建模与变更管理办法",
            code="YN-LC-1.0.0",
            version="A/0",
            category="流程管理",
            org_scope="所有配置在OA、ERP、供应链和人力系统中的审批流程",
            status="effective",
            effective_date="2026-01-15",
            clauses=[
                _pc("policy_process_governance", "proc_gov_1", "1", "目的", "为规范审批流程建模、BPMN文件管理、节点角色、条件分支、系统配置和变更发布，确保流程配置与制度依据一致。", 1),
                _pc("policy_process_governance", "proc_gov_2_1", "2.1", "流程资产", "审批流程应以BPMN文件作为结构化资产保存，流程节点应包含节点名称、办理角色、动作、触发条件和对应制度依据。", 2),
                _pc("policy_process_governance", "proc_gov_2_2", "2.2", "制度依据", "新增审批节点、删除审批节点、调整审批主体或金额条件时，流程管理员必须引用现行有效制度条款作为依据。无制度依据的节点不得发布上线。", 3),
                _pc("policy_process_governance", "proc_gov_3_1", "3.1", "流程变更申请", "流程变更由业务归口部门发起，提交变更原因、影响制度、节点清单、角色清单、测试记录和回滚方案。", 4),
                _pc("policy_process_governance", "proc_gov_3_2", "3.2", "会签要求", "涉及审批权限、风控节点、合同用印、财务付款或员工权益的流程变更，应由制度管理办公室、风控合规部、法务部或人力资源部按职责会签。", 5),
                _pc("policy_process_governance", "proc_gov_4_1", "4.1", "上线控制", "流程管理员完成系统配置后，应由业务归口部门进行UAT验证；信息技术部仅负责技术发布，不得替代业务审批或制度复核。", 6),
                _pc("policy_process_governance", "proc_gov_4_2", "4.2", "版本管理", "BPMN流程图应保留历史版本。新流程版本上线后默认生效，历史风险记录不自动重跑，但应标注所依据的流程版本。", 7),
            ],
        ),
        PolicyDocument(
            id="policy_exception_authorization",
            name="制度例外事项授权与追踪办法",
            code="YN-ZD-3.0.0",
            version="A/0",
            category="制度管理",
            org_scope="平台公司及下属企业",
            status="effective",
            effective_date="2026-04-01",
            clauses=[
                _pc("policy_exception_authorization", "inst_exc_1", "1", "目的", "为规范偏离制度要求的例外事项审批、记录、追踪和复盘，防止制度执行被长期绕开。", 1),
                _pc("policy_exception_authorization", "inst_exc_2_1", "2.1", "例外定义", "例外事项包括未按制度流程审批、临时调整审批主体、跳过风控或法务节点、使用历史版本依据、超授权先执行后补批等情形。", 2),
                _pc("policy_exception_authorization", "inst_exc_3_1", "3.1", "审批要求", "一般例外事项由业务归口部门负责人审核、制度管理办公室复核、业务分管领导审批；重大例外事项应提交平台总经理审批。", 3),
                _pc("policy_exception_authorization", "inst_exc_3_2", "3.2", "禁止事项", "涉及关联交易、重大资金支付、员工权益调整、法律争议处理和监管报送的例外事项，不得跳过风控合规部或法务部会签。", 4),
                _pc("policy_exception_authorization", "inst_exc_4_1", "4.1", "追踪复盘", "制度管理办公室每月汇总例外事项，识别重复例外、长期例外和制度设计缺陷，并推动修订制度或流程。", 5),
            ],
        ),
    ]

    policy_by_id = {policy.id: policy for policy in policies}
    policy_version_history = [
        PolicyVersion(
            id="policy_version_policy_institution_governance_C_2",
            policy_id="policy_institution_governance",
            version_no="C/2",
            effective_date="2025-05-01",
            status="historical",
            created_at="2025-05-01T09:00:00+08:00",
            created_by="制度管理办公室",
            change_summary="旧版未覆盖AI辅助解析、低置信度版本匹配和历史风险版本提示。",
            metadata={"name": "制度建设与管理办法", "code": "YN-ZD-1.0.0", "category": "制度管理", "org_scope": "平台公司及下属企业"},
            clauses=policy_by_id["policy_institution_governance"].clauses[:12],
        ),
        PolicyVersion(
            id="policy_version_policy_institution_publish_B_1",
            policy_id="policy_institution_publish",
            version_no="B/1",
            effective_date="2025-10-15",
            status="historical",
            created_at="2025-10-15T10:30:00+08:00",
            created_by="制度管理员",
            change_summary="补充源文件留存要求，但尚未明确历史版本风险提示和低置信度匹配确认。",
            metadata={"name": "制度发布与版本控制实施细则", "code": "YN-ZD-1.1.0", "category": "制度管理", "org_scope": "平台制度管理办公室、各业务归口部门"},
            clauses=policy_by_id["policy_institution_publish"].clauses[:7],
        ),
        PolicyVersion(
            id="policy_version_policy_purchase_A_N",
            policy_id="policy_purchase",
            version_no="A/N",
            effective_date="2025-06-01",
            status="historical",
            created_at="2025-06-01T09:30:00+08:00",
            created_by="采购中心",
            change_summary="旧版仅覆盖点价审批，未写明战略物资、关联供应商和50万元以上风控复核。",
            metadata={"name": "饲料原料基差采购业务工作细则", "code": "YN-CZ-6.3.5", "category": "招采管理", "org_scope": "平台采购中心、饲料产品部及下属饲料厂"},
            clauses=policy_by_id["policy_purchase"].clauses[:13],
        ),
    ]

    purchase_nodes = [
        _node("process_purchase", "purchase_apply", "task_apply", "提交基差采购申请", "饲料厂采购员", "提交", 1),
        _node("process_purchase", "purchase_product_review", "task_product_review", "需求与库存复核", "饲料产品部经理", "审核", 2),
        _node("process_purchase", "purchase_quote", "task_quote", "供应商报价汇总", "采购专员", "汇总", 3),
        _node("process_purchase", "purchase_dept", "task_dept_review", "部门负责人审核", "部门负责人", "审核", 4, "金额超过30万元"),
        _node("process_purchase", "purchase_general", "task_general_approval", "平台总经理审批", "平台总经理", "审批", 5, "金额超过30万元"),
        _node("process_purchase", "purchase_chair", "task_chair_approval", "平台董事长审批", "平台董事长", "审批", 6, "金额超过30万元"),
        _node("process_purchase", "purchase_price", "task_price_instruction", "发送点价指令", "采购中心采购岗", "执行", 7),
        _node("process_purchase", "purchase_seal", "task_seal", "点价确认单用印", "印章管理员", "用印", 8),
        _node("process_purchase", "purchase_order", "task_order", "生成采购订单", "采购实施岗", "生成", 9),
        _node("process_purchase", "purchase_archive", "task_archive", "采购资料归档", "采购实施岗", "归档", 10),
    ]
    sub_purchase_nodes = [
        _node("process_sub_purchase", "sub_apply", "task_sub_apply", "子公司采购申请", "经办人", "提交", 1),
        _node("process_sub_purchase", "sub_factory_review", "task_sub_factory_review", "饲料厂厂长审核", "饲料厂厂长", "审核", 2),
        _node("process_sub_purchase", "sub_general", "task_sub_general", "子公司总经理审批", "子公司总经理", "审批", 3, "金额超过50万元"),
        _node("process_sub_purchase", "sub_contract", "task_sub_contract", "合同确认", "采购实施部门", "确认", 4),
        _node("process_sub_purchase", "sub_record", "task_platform_record", "平台备案", "平台采购部", "备案", 5, "金额超过100万元"),
    ]
    supplier_nodes = [
        _node("process_supplier", "supplier_apply", "task_supplier_apply", "发起供应商准入", "采购员", "提交", 1),
        _node("process_supplier", "supplier_purchase_check", "task_supplier_purchase_check", "采购中心初审", "采购中心", "审核", 2),
        _node("process_supplier", "supplier_quality", "task_supplier_quality", "质量评估", "质量经理", "审核", 3, "生产厂家"),
        _node("process_supplier", "supplier_master", "task_supplier_master", "供应商主数据建档", "供应商主数据专员", "建档", 4),
        _node("process_supplier", "supplier_enable", "task_supplier_enable", "启用供应商", "采购中心", "启用", 5),
    ]
    contract_nodes = [
        _node("process_contract", "contract_apply", "task_contract_apply", "合同发起", "业务经办人", "提交", 1),
        _node("process_contract", "contract_dept", "task_contract_dept", "部门负责人审核", "部门负责人", "审核", 2),
        _node("process_contract", "contract_legal", "task_contract_legal", "法务专员审查", "法务专员", "审查", 3, "非标合同或金额超过50万元"),
        _node("process_contract", "contract_finance", "task_contract_finance", "财务复核", "财务共享中心", "复核", 4, "付款比例超过50%"),
        _node("process_contract", "contract_seal", "task_contract_seal", "合同用印", "印章管理员", "用印", 5),
        _node("process_contract", "contract_archive", "task_contract_archive", "合同归档", "业务经办人", "归档", 6),
    ]
    recruit_nodes = [
        _node("process_recruit", "recruit_apply", "task_recruit_apply", "提交录用申请", "人力专员", "提交", 1),
        _node("process_recruit", "recruit_hiring_mgr", "task_hiring_mgr", "用人部门经理确认", "用人部门经理", "审核", 2),
        _node("process_recruit", "recruit_hrbp", "task_hrbp_review", "HRBP复核", "HRBP", "审核", 3),
        _node("process_recruit", "recruit_salary", "task_salary_approval", "定薪审批", "薪酬经理", "审批", 4),
        _node("process_recruit", "recruit_leader", "task_leader_approval", "分管领导审批", "分管领导", "审批", 5),
        _node("process_recruit", "recruit_general", "task_general_final", "平台总经理终批", "平台总经理", "审批", 6, "关键岗位"),
        _node("process_recruit", "recruit_notice", "task_offer_notice", "发放录用通知", "人力专员", "通知", 7),
    ]
    institution_publish_nodes = [
        _node("process_institution_publish", "inst_pub_apply", "task_inst_pub_apply", "提交制度立项申请", "业务归口部门经办人", "提交", 1),
        _node("process_institution_publish", "inst_pub_owner_review", "task_inst_pub_owner_review", "业务归口部门负责人审核", "业务归口部门负责人", "审核", 2),
        _node("process_institution_publish", "inst_pub_office_review", "task_inst_pub_office_review", "制度管理办公室复核", "制度管理办公室", "复核", 3),
        _node("process_institution_publish", "inst_pub_legal", "task_inst_pub_legal", "法务部会签", "法务部", "会签", 4, "涉及合同、用印、劳动关系或数据合规"),
        _node("process_institution_publish", "inst_pub_risk", "task_inst_pub_risk", "风控合规部会签", "风控合规部", "会签", 5, "涉及采购、资金、销售、数据、关联交易或重大授权"),
        _node("process_institution_publish", "inst_pub_it_config", "task_inst_pub_it_config", "制度树与知识库配置", "信息技术部", "配置", 6),
        _node("process_institution_publish", "inst_pub_general", "task_inst_pub_general", "平台总经理审批", "平台总经理", "审批", 7, "管理办法"),
        _node("process_institution_publish", "inst_pub_notice", "task_inst_pub_notice", "发布公告", "制度管理员", "发布", 8),
        _node("process_institution_publish", "inst_pub_train", "task_inst_pub_train", "宣贯培训记录归档", "业务归口部门经办人", "归档", 9),
    ]
    institution_revision_nodes = [
        _node("process_institution_revision", "inst_rev_upload", "task_inst_rev_upload", "上传修订稿", "制度管理员", "提交", 1),
        _node("process_institution_revision", "inst_rev_match", "task_inst_rev_match", "版本匹配确认", "制度管理办公室", "确认", 2, "低置信度匹配"),
        _node("process_institution_revision", "inst_rev_business", "task_inst_rev_business", "业务差异说明审核", "业务归口部门负责人", "审核", 3),
        _node("process_institution_revision", "inst_rev_ai_check", "task_inst_rev_ai_check", "AI一致性检查", "AI助手", "检查", 4),
        _node("process_institution_revision", "inst_rev_office", "task_inst_rev_office", "版本台账复核", "制度管理办公室", "复核", 5),
        _node("process_institution_revision", "inst_rev_leader", "task_inst_rev_leader", "业务分管领导审批", "业务分管领导", "审批", 6),
        _node("process_institution_revision", "inst_rev_publish", "task_inst_rev_publish", "默认生效发布", "制度管理员", "发布", 7),
    ]
    institution_abolish_nodes = [
        _node("process_institution_abolish", "inst_ab_apply", "task_inst_ab_apply", "提交制度废止申请", "业务归口部门经办人", "提交", 1),
        _node("process_institution_abolish", "inst_ab_replace", "task_inst_ab_replace", "替代文件确认", "业务归口部门负责人", "确认", 2),
        _node("process_institution_abolish", "inst_ab_office", "task_inst_ab_office", "制度管理办公室复核", "制度管理办公室", "复核", 3),
        _node("process_institution_abolish", "inst_ab_leader", "task_inst_ab_leader", "业务分管领导审核", "业务分管领导", "审核", 4),
        _node("process_institution_abolish", "inst_ab_general", "task_inst_ab_general", "平台总经理审批", "平台总经理", "审批", 5),
        _node("process_institution_abolish", "inst_ab_it_archive", "task_inst_ab_it_archive", "系统下架与归档", "信息技术部", "下架", 6),
    ]
    institution_annual_review_nodes = [
        _node("process_institution_annual_review", "inst_ar_plan", "task_inst_ar_plan", "发起年度复核计划", "制度管理办公室", "发起", 1),
        _node("process_institution_annual_review", "inst_ar_self", "task_inst_ar_self", "业务部门自评", "业务归口部门负责人", "评价", 2),
        _node("process_institution_annual_review", "inst_ar_office_check", "task_inst_ar_office_check", "目录版本一致性检查", "制度管理员", "检查", 3),
        _node("process_institution_annual_review", "inst_ar_risk_sample", "task_inst_ar_risk_sample", "高风险制度抽查", "风控合规部", "抽查", 4, "采购、资金、合同、人力、数据"),
        _node("process_institution_annual_review", "inst_ar_rectify", "task_inst_ar_rectify", "整改计划确认", "责任部门负责人", "确认", 5),
        _node("process_institution_annual_review", "inst_ar_delay", "task_inst_ar_delay", "逾期整改督办", "业务分管领导", "督办", 6, "逾期超过30日"),
        _node("process_institution_annual_review", "inst_ar_close", "task_inst_ar_close", "复核关闭", "制度管理办公室", "关闭", 7),
    ]
    process_change_nodes = [
        _node("process_process_change", "proc_change_apply", "task_proc_change_apply", "提交流程变更申请", "流程管理员", "提交", 1),
        _node("process_process_change", "proc_change_config", "task_proc_change_config", "系统配置变更", "信息技术部", "配置", 2),
        _node("process_process_change", "proc_change_uat", "task_proc_change_uat", "UAT验证", "业务归口部门经办人", "验证", 3),
        _node("process_process_change", "proc_change_publish", "task_proc_change_publish", "上线发布", "流程管理员", "发布", 4),
        _node("process_process_change", "proc_change_archive", "task_proc_change_archive", "BPMN归档", "流程管理员", "归档", 5),
    ]

    processes = [
        _process("process_purchase", "饲料原料基差采购审批流程", "BPMN-CG-001", "采购", "平台及下属饲料厂", "饲料原料基差采购审批流程.bpmn", purchase_nodes),
        _process("process_sub_purchase", "子公司普通采购审批流程", "BPMN-ZCG-001", "采购", "子公司", "子公司普通采购审批流程.bpmn", sub_purchase_nodes),
        _process("process_supplier", "供应商准入流程", "BPMN-GY-001", "供应商管理", "平台及子公司", "供应商准入流程.bpmn", supplier_nodes),
        _process("process_contract", "采购合同用印审批流程", "BPMN-FW-001", "合同法务", "平台及子公司", "采购合同用印审批流程.bpmn", contract_nodes),
        _process("process_recruit", "招聘录用与定薪审批流程", "BPMN-HR-001", "人力", "平台及子公司", "招聘录用与定薪审批流程.bpmn", recruit_nodes),
        _process("process_institution_publish", "制度新建发布审批流程", "BPMN-ZD-001", "制度管理", "平台及下属企业", "制度新建发布审批流程.bpmn", institution_publish_nodes),
        _process("process_institution_revision", "制度修订版本发布流程", "BPMN-ZD-002", "制度管理", "平台及下属企业", "制度修订版本发布流程.bpmn", institution_revision_nodes),
        _process("process_institution_abolish", "制度废止审批流程", "BPMN-ZD-003", "制度管理", "平台及下属企业", "制度废止审批流程.bpmn", institution_abolish_nodes),
        _process("process_institution_annual_review", "制度年度复核整改流程", "BPMN-ZD-004", "制度管理", "平台及下属企业", "制度年度复核整改流程.bpmn", institution_annual_review_nodes),
        _process("process_process_change", "审批流程变更上线流程", "BPMN-LC-001", "流程管理", "平台及下属企业", "审批流程变更上线流程.bpmn", process_change_nodes),
    ]
    process_by_id = {process.id: process for process in processes}
    process_version_history = [
        ProcessVersion(
            id="process_version_process_institution_publish_v0_9",
            process_id="process_institution_publish",
            version_no="v0.9",
            effective_date="2025-09-01",
            status="historical",
            created_at="2025-09-01T11:00:00+08:00",
            created_by="流程管理员",
            change_summary="旧版制度发布流程缺少风控合规会签和培训归档节点。",
            metadata={"name": "制度新建发布审批流程", "code": "BPMN-ZD-001", "business_domain": "制度管理", "org_scope": "平台及下属企业"},
            nodes=[node for node in process_by_id["process_institution_publish"].nodes if node.id not in {"node_inst_pub_risk", "node_inst_pub_train"}],
            asset=process_by_id["process_institution_publish"].asset,
        ),
        ProcessVersion(
            id="process_version_process_process_change_v0_8",
            process_id="process_process_change",
            version_no="v0.8",
            effective_date="2025-11-01",
            status="historical",
            created_at="2025-11-01T14:00:00+08:00",
            created_by="信息技术部",
            change_summary="旧版由信息技术部直接配置上线，未记录制度依据和UAT验证。",
            metadata={"name": "审批流程变更上线流程", "code": "BPMN-LC-001", "business_domain": "流程管理", "org_scope": "平台及下属企业"},
            nodes=process_by_id["process_process_change"].nodes[:2],
            asset=process_by_id["process_process_change"].asset,
        ),
    ]

    knowledge_nodes = [
        KnowledgeNode(id="kg_role_purchase_center", node_type="人员角色", name="采购中心", source_count=12),
        KnowledgeNode(id="kg_role_decision_group", node_type="人员角色", name="饲料原料采购决策小组", source_count=4),
        KnowledgeNode(id="kg_role_risk", node_type="人员角色", name="风控合规部", source_count=5),
        KnowledgeNode(id="kg_role_legal", node_type="人员角色", name="法务部", source_count=4),
        KnowledgeNode(id="kg_role_general", node_type="人员角色", name="平台总经理", source_count=5),
        KnowledgeNode(id="kg_role_sub_general", node_type="人员角色", name="子公司总经理", source_count=2),
        KnowledgeNode(id="kg_role_supplier_office", node_type="人员角色", name="供应商管理办公室", source_count=3),
        KnowledgeNode(id="kg_role_quality", node_type="人员角色", name="质量管理部", source_count=2),
        KnowledgeNode(id="kg_role_hr_leader", node_type="人员角色", name="人力资源负责人", source_count=4),
        KnowledgeNode(id="kg_role_salary_committee", node_type="人员角色", name="薪酬委员会", source_count=2),
        KnowledgeNode(id="kg_role_institution_office", node_type="人员角色", name="制度管理办公室", source_count=14),
        KnowledgeNode(id="kg_role_institution_admin", node_type="人员角色", name="制度管理员", source_count=9),
        KnowledgeNode(id="kg_role_business_owner", node_type="人员角色", name="业务归口部门负责人", source_count=8),
        KnowledgeNode(id="kg_role_business_leader", node_type="人员角色", name="业务分管领导", source_count=7),
        KnowledgeNode(id="kg_role_process_admin", node_type="人员角色", name="流程管理员", source_count=5),
        KnowledgeNode(id="kg_role_it_department", node_type="人员角色", name="信息技术部", source_count=5),
        KnowledgeNode(id="kg_role_finance_ops", node_type="人员角色", name="财务运营部", source_count=3),
        KnowledgeNode(id="kg_role_responsible_dept", node_type="人员角色", name="责任部门负责人", source_count=2),
        KnowledgeNode(id="kg_org_feed_product", node_type="部门组织", name="饲料产品部", source_count=3),
        KnowledgeNode(id="kg_org_institution_tree", node_type="部门组织", name="制度树", source_count=3),
        KnowledgeNode(id="kg_rule_purchase_risk", node_type="业务规则", name="战略物资或超过50万元采购需风控复核", source_count=3),
        KnowledgeNode(id="kg_rule_contract_legal", node_type="业务规则", name="非标或超过30万元合同需法务审查", source_count=2),
        KnowledgeNode(id="kg_rule_salary_scope", node_type="业务规则", name="薪酬定级指引仅覆盖平台本部正式员工", source_count=1),
        KnowledgeNode(id="kg_rule_policy_version_default", node_type="业务规则", name="新版本发布后默认生效且历史风险不自动重跑", source_count=4),
        KnowledgeNode(id="kg_rule_policy_low_confidence", node_type="业务规则", name="制度低置信度版本匹配必须人工确认", source_count=2),
        KnowledgeNode(id="kg_rule_process_basis", node_type="业务规则", name="审批流节点必须引用现行制度依据", source_count=3),
        KnowledgeNode(id="kg_rule_policy_annual_review", node_type="业务规则", name="制度年度复核需检查流程匹配和角色一致性", source_count=2),
    ]
    knowledge_edges = [
        KnowledgeEdge(id="edge_rule_purchase_risk", source="kg_rule_purchase_risk", target="kg_role_risk", edge_type="requires_role"),
        KnowledgeEdge(id="edge_rule_contract_legal", source="kg_rule_contract_legal", target="kg_role_legal", edge_type="requires_role"),
        KnowledgeEdge(id="edge_rule_salary_scope", source="kg_rule_salary_scope", target="kg_role_salary_committee", edge_type="exception_review"),
        KnowledgeEdge(id="edge_rule_policy_version_default", source="kg_rule_policy_version_default", target="kg_role_institution_office", edge_type="owner"),
        KnowledgeEdge(id="edge_rule_policy_low_confidence", source="kg_rule_policy_low_confidence", target="kg_role_institution_admin", edge_type="requires_confirmation"),
        KnowledgeEdge(id="edge_rule_process_basis", source="kg_rule_process_basis", target="kg_role_process_admin", edge_type="control_requirement"),
        KnowledgeEdge(id="edge_rule_policy_annual_review", source="kg_rule_policy_annual_review", target="kg_role_business_owner", edge_type="requires_role"),
    ]

    findings = [
        Finding(
            id="finding_conflict_threshold",
            finding_type="policy_conflict",
            title="基差采购审批阈值与审批主体冲突",
            description="基差采购细则要求30万元以上提交平台总经理审批，子公司细则规定50万元以上由子公司总经理审批；两份制度在子公司饲料原料采购场景中存在适用范围重叠。",
            severity="high",
            confidence=0.86,
            skill_id="skill_policy_conflict",
            target_ids=["policy_purchase", "policy_sub_purchase"],
            evidence=[
                Evidence(id="ev_purchase_30w", source_type="policy_clause", source_id="clause_basis_7_1_1", label="饲料原料基差采购业务工作细则 7.1.1", quote="单笔基差采购金额超过30万元的，应由采购部门负责人审核后提交平台总经理审批。"),
                Evidence(id="ev_sub_50w", source_type="policy_clause", source_id="clause_sub_purchase_2_1", label="子公司采购实施细则 第二条第一款", quote="单笔采购金额超过50万元的，由子公司总经理审批；超过100万元的，报平台采购部备案。"),
            ],
            assumption="两份制度均被选入本次采购场景，且基差采购发生在子公司饲料厂时存在制度适用交叉。",
            suggestion="建议明确基差采购优先适用专项细则，或在子公司细则中排除平台统采和基差采购。同步更新审批矩阵。",
        ),
        Finding(
            id="finding_missing_risk_review",
            finding_type="missing_process_node",
            title="基差采购流程缺少风控复核节点",
            description="制度要求战略物资、关联供应商或金额超过50万元时增加风控复核，当前BPMN未配置风控合规部复核节点。",
            severity="high",
            confidence=0.84,
            skill_id="skill_policy_process_check",
            target_ids=["policy_purchase", "process_purchase"],
            evidence=[
                Evidence(id="ev_purchase_risk_clause", source_type="policy_clause", source_id="clause_basis_7_1_1", label="饲料原料基差采购业务工作细则 7.1.1", quote="涉及战略物资、关联供应商或单笔金额超过50万元的采购事项，应增加风控复核节点。"),
                Evidence(id="ev_purchase_bpmn_nodes", source_type="bpmn_node", source_id="process_purchase", label="饲料原料基差采购审批流程 BPMN", quote="当前节点包含需求复核、报价汇总、部门负责人审核、平台总经理审批、平台董事长审批、点价指令、用印、订单和归档。"),
            ],
            assumption="当前BPMN代表基差采购正式审批流，金额和战略物资条件未在其他子流程中单独处理。",
            suggestion="在平台总经理审批前增加“风控合规部复核”节点，并设置金额超过50万元、战略物资、关联供应商三个触发条件。",
        ),
        Finding(
            id="finding_extra_chair_approval",
            finding_type="extra_process_node",
            title="流程存在制度未要求的平台董事长审批节点",
            description="所选制度要求平台总经理审批和招采委员会审议，但未要求30万元以上均提交平台董事长审批，当前流程增加董事长审批可能造成授权链条混乱。",
            severity="medium",
            confidence=0.78,
            skill_id="skill_policy_process_check",
            target_ids=["policy_purchase", "policy_purchase_platform", "process_purchase"],
            evidence=[
                Evidence(id="ev_purchase_general_clause", source_type="policy_clause", source_id="clause_basis_7_1_1", label="饲料原料基差采购业务工作细则 7.1.1", quote="单笔基差采购金额超过30万元的，应由采购部门负责人审核后提交平台总经理审批。"),
                Evidence(id="ev_purchase_chair_node", source_type="bpmn_node", source_id="node_purchase_chair", label="饲料原料基差采购审批流程 节点", quote="平台董事长审批 / 平台董事长审批 / 金额超过30万元。"),
            ],
            assumption="本次所选制度范围内未提供平台董事长对该场景的直接授权条款。",
            suggestion="删除董事长审批节点，或将其调整为超过200万元且招采委员会审议后的例外审批，并补充对应制度依据。",
        ),
        Finding(
            id="finding_salary_no_basis",
            finding_type="no_policy_basis",
            title="招聘流程中的定薪审批缺少子公司制度依据",
            description="招聘流程包含定薪审批，但薪酬定级指引仅覆盖平台本部正式员工；子公司参照执行需要另行制定细则，当前制度范围无法支撑该节点。",
            severity="high",
            confidence=0.82,
            skill_id="skill_policy_process_check",
            target_ids=["process_recruit", "policy_recruit", "policy_salary"],
            evidence=[
                Evidence(id="ev_recruit_salary_node", source_type="bpmn_node", source_id="node_recruit_salary", label="招聘录用与定薪审批流程 节点", quote="定薪审批 / 薪酬经理审批。"),
                Evidence(id="ev_salary_scope", source_type="policy_clause", source_id="clause_salary_2_1", label="薪酬定级管理指引 第二条第一款", quote="薪酬定级适用于平台本部正式员工，子公司参照执行但需另行制定细则。"),
            ],
            assumption="当前流程适用于平台及子公司，但所选薪酬制度没有提供子公司定薪审批细则。",
            suggestion="补充子公司定薪审批制度或将定薪审批拆分为适用平台本部的独立薪酬流程。",
        ),
        Finding(
            id="finding_policy_effective_date_conflict",
            finding_type="policy_conflict",
            title="制度新版本默认生效与五个工作日后生效口径冲突",
            description="制度建设与管理办法要求新版本审批发布后默认为当前生效版本，发布细则又规定原则上发布五个工作日后生效；如正文未明确即时生效，执行人员可能无法判断当前版本何时替代历史版本。",
            severity="medium",
            confidence=0.83,
            skill_id="skill_policy_conflict",
            target_ids=["policy_institution_governance", "policy_institution_publish"],
            evidence=[
                Evidence(id="ev_inst_default_current", source_type="policy_clause", source_id="clause_inst_gov_6_2", label="制度建设与管理办法 6.2", quote="新版本制度经审批发布后默认为当前生效版本；历史版本自动转为失效或归档状态。"),
                Evidence(id="ev_inst_publish_5days", source_type="policy_clause", source_id="clause_inst_pub_3_1", label="制度发布与版本控制实施细则 3.1", quote="制度发布后原则上在五个工作日后生效；制度正文明确即时生效或审批意见要求即时生效的，可在发布当日生效。"),
            ],
            assumption="两份制度均适用于制度发布和版本切换场景，且未通过更明确的优先级条款消除生效时间差异。",
            suggestion="建议将“默认生效”明确为系统默认选中当前版本，但业务生效日期以正文或发布公告为准；前端弹窗提示当前版本与业务生效日期的差异。",
        ),
        Finding(
            id="finding_process_change_missing_review",
            finding_type="missing_process_node",
            title="审批流程变更上线流程缺少制度复核和风险会签",
            description="流程管理办法要求涉及审批权限、风控节点、合同用印、财务付款或员工权益的流程变更需制度管理办公室及相关部门会签，当前流程变更上线流程从系统配置直接进入UAT和发布，缺少制度依据复核。",
            severity="high",
            confidence=0.87,
            skill_id="skill_policy_process_check",
            target_ids=["policy_process_governance", "process_process_change"],
            evidence=[
                Evidence(id="ev_proc_change_cosign", source_type="policy_clause", source_id="clause_proc_gov_3_2", label="审批流程建模与变更管理办法 3.2", quote="涉及审批权限、风控节点、合同用印、财务付款或员工权益的流程变更，应由制度管理办公室、风控合规部、法务部或人力资源部按职责会签。"),
                Evidence(id="ev_proc_change_nodes", source_type="bpmn_node", source_id="process_process_change", label="审批流程变更上线流程 BPMN", quote="当前节点为提交流程变更申请、系统配置变更、UAT验证、上线发布、BPMN归档。"),
            ],
            assumption="当前BPMN代表审批流程变更正式上线流程，且所选制度为流程变更依据。",
            suggestion="在系统配置变更前增加制度管理办公室复核节点，并按变更类型增加风控、法务、财务或人力会签分支。",
        ),
        Finding(
            id="finding_ai_check_no_basis",
            finding_type="no_policy_basis",
            title="制度修订流程中的AI一致性检查缺少制度依据",
            description="制度修订版本发布流程包含“AI一致性检查”节点，但制度管理相关制度仅要求制度冲突跟踪、版本匹配和流程关联更新，未明确AI检查作为正式审批或检查节点的职责、输出和责任边界。",
            severity="medium",
            confidence=0.78,
            skill_id="skill_policy_process_check",
            target_ids=["policy_institution_governance", "policy_institution_publish", "process_institution_revision"],
            evidence=[
                Evidence(id="ev_ai_check_node", source_type="bpmn_node", source_id="node_inst_rev_ai_check", label="制度修订版本发布流程 节点", quote="AI一致性检查 / AI助手 / 检查。"),
                Evidence(id="ev_inst_low_confidence", source_type="policy_clause", source_id="clause_inst_pub_3_3", label="制度发布与版本控制实施细则 3.3", quote="低置信度匹配必须由制度管理员人工确认后方可入库。"),
            ],
            assumption="AI助手节点被配置为正式流程节点，而不是后台辅助分析日志。",
            suggestion="明确AI一致性检查的制度依据、输出格式、人工复核责任和失败处理规则；或将其调整为后台辅助步骤，不作为审批流正式节点。",
        ),
        Finding(
            id="finding_publish_it_before_approval",
            finding_type="process_order_risk",
            title="制度发布流程在总经理审批前配置制度树和知识库",
            description="制度新建发布审批流程将“制度树与知识库配置”放在平台总经理审批之前，可能导致未获批制度提前进入系统资产和知识库，影响后续任务依据。",
            severity="medium",
            confidence=0.8,
            skill_id="skill_policy_process_check",
            target_ids=["policy_institution_governance", "process_institution_publish"],
            evidence=[
                Evidence(id="ev_inst_publish_after_approval", source_type="policy_clause", source_id="clause_inst_gov_6_3", label="制度建设与管理办法 6.3", quote="制度发布应同步更新制度树、版本台账、流程关联关系和角色清单。"),
                Evidence(id="ev_inst_pub_it_node", source_type="bpmn_node", source_id="node_inst_pub_it_config", label="制度新建发布审批流程 节点", quote="制度树与知识库配置 / 信息技术部 / 配置。"),
            ],
            assumption="制度树和知识库配置代表正式发布资产，而不是预发布草稿环境。",
            suggestion="将制度树、版本台账和知识库配置移动到审批通过之后，或明确该节点仅写入草稿区且不可被任务引用。",
        ),
    ]

    return {
        "policies": policies,
        "processes": processes,
        "knowledge_nodes": knowledge_nodes,
        "knowledge_edges": knowledge_edges,
        "policy_version_history": policy_version_history,
        "process_version_history": process_version_history,
        "findings": findings,
    }
