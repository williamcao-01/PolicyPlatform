from __future__ import annotations

import html
import io
import zipfile
from datetime import UTC, datetime

from app.models import Finding


def findings_workbook(findings: list[Finding]) -> bytes:
    rows = [
        [
            "风险标题",
            "严重程度",
            "状态",
            "风险描述",
            "整改建议",
            "证据来源",
            "证据摘录",
        ]
    ]
    for finding in findings:
        evidence_label = "\n".join(item.label for item in finding.evidence)
        evidence_quote = "\n".join(item.quote for item in finding.evidence)
        rows.append(
            [
                finding.title,
                finding.severity,
                finding.status,
                finding.description,
                finding.suggestion,
                evidence_label,
                evidence_quote,
            ]
        )
    return _xlsx(rows)


def _xlsx(rows: list[list[str]]) -> bytes:
    created = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sheet_xml = _sheet_xml(rows)
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="待解决风险" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>"""
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>"""
    core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>待解决风险清单</dc:title><dc:creator>AI 制度治理工作台</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created></cp:coreProperties>"""
    app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>AI 制度治理工作台</Application></Properties>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        workbook.writestr("docProps/core.xml", core_xml)
        workbook.writestr("docProps/app.xml", app_xml)
    return buffer.getvalue()


def _sheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    widths = "".join(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>' for index, width in enumerate([24, 12, 16, 42, 42, 34, 56], start=1))
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            safe_value = html.escape(str(value or ""), quote=False)
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{safe_value}</t></is></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>{widths}</cols><sheetData>{"".join(row_xml)}</sheetData></worksheet>"""


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
