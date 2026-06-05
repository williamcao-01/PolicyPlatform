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

    processes = [
        _process("process_purchase", "饲料原料基差采购审批流程", "BPMN-CG-001", "采购", "平台及下属饲料厂", "饲料原料基差采购审批流程.bpmn", purchase_nodes),
        _process("process_sub_purchase", "子公司普通采购审批流程", "BPMN-ZCG-001", "采购", "子公司", "子公司普通采购审批流程.bpmn", sub_purchase_nodes),
        _process("process_supplier", "供应商准入流程", "BPMN-GY-001", "供应商管理", "平台及子公司", "供应商准入流程.bpmn", supplier_nodes),
        _process("process_contract", "采购合同用印审批流程", "BPMN-FW-001", "合同法务", "平台及子公司", "采购合同用印审批流程.bpmn", contract_nodes),
        _process("process_recruit", "招聘录用与定薪审批流程", "BPMN-HR-001", "人力", "平台及子公司", "招聘录用与定薪审批流程.bpmn", recruit_nodes),
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
        KnowledgeNode(id="kg_org_feed_product", node_type="部门组织", name="饲料产品部", source_count=3),
        KnowledgeNode(id="kg_rule_purchase_risk", node_type="业务规则", name="战略物资或超过50万元采购需风控复核", source_count=3),
        KnowledgeNode(id="kg_rule_contract_legal", node_type="业务规则", name="非标或超过30万元合同需法务审查", source_count=2),
        KnowledgeNode(id="kg_rule_salary_scope", node_type="业务规则", name="薪酬定级指引仅覆盖平台本部正式员工", source_count=1),
    ]
    knowledge_edges = [
        KnowledgeEdge(id="edge_rule_purchase_risk", source="kg_rule_purchase_risk", target="kg_role_risk", edge_type="requires_role"),
        KnowledgeEdge(id="edge_rule_contract_legal", source="kg_rule_contract_legal", target="kg_role_legal", edge_type="requires_role"),
        KnowledgeEdge(id="edge_rule_salary_scope", source="kg_rule_salary_scope", target="kg_role_salary_committee", edge_type="exception_review"),
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
            skill_id="skill_no_policy_basis",
            target_ids=["process_recruit", "policy_recruit", "policy_salary"],
            evidence=[
                Evidence(id="ev_recruit_salary_node", source_type="bpmn_node", source_id="node_recruit_salary", label="招聘录用与定薪审批流程 节点", quote="定薪审批 / 薪酬经理审批。"),
                Evidence(id="ev_salary_scope", source_type="policy_clause", source_id="clause_salary_2_1", label="薪酬定级管理指引 第二条第一款", quote="薪酬定级适用于平台本部正式员工，子公司参照执行但需另行制定细则。"),
            ],
            assumption="当前流程适用于平台及子公司，但所选薪酬制度没有提供子公司定薪审批细则。",
            suggestion="补充子公司定薪审批制度或将定薪审批拆分为适用平台本部的独立薪酬流程。",
        ),
    ]

    return {
        "policies": policies,
        "processes": processes,
        "knowledge_nodes": knowledge_nodes,
        "knowledge_edges": knowledge_edges,
        "findings": findings,
    }
