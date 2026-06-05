import type { Finding } from './types';

export function downloadFindingsWorkbook(findings: Finding[], fileName: string) {
  const rows = [
    ['风险标题', '严重程度', '状态', '风险描述', '整改建议', '证据来源', '证据摘录'],
    ...findings.map((finding) => [
      finding.title,
      finding.severity,
      finding.status,
      finding.description,
      finding.suggestion,
      finding.evidence.map((item) => item.label).join('\n'),
      finding.evidence.map((item) => item.quote).join('\n')
    ])
  ];
  const blob = new Blob([xlsx(rows)], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function xlsx(rows: string[][]) {
  const files: Record<string, string> = {
    '[Content_Types].xml':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    '_rels/.rels':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="输出结果" sheetId="1" r:id="rId1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels':
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    'xl/worksheets/sheet1.xml': sheetXml(rows)
  };
  return zip(files);
}

function sheetXml(rows: string[][]) {
  const colWidths = [24, 12, 16, 42, 42, 34, 56]
    .map((width, index) => `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`)
    .join('');
  const rowXml = rows
    .map((row, rowIndex) => {
      const cells = row
        .map((value, colIndex) => {
          const ref = `${columnName(colIndex + 1)}${rowIndex + 1}`;
          return `<c r="${ref}" t="inlineStr"><is><t>${escapeXml(value)}</t></is></c>`;
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cells}</row>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>${colWidths}</cols><sheetData>${rowXml}</sheetData></worksheet>`;
}

function zip(files: Record<string, string>) {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;
  let index = 0;
  for (const [name, content] of Object.entries(files)) {
    const nameBytes = bytes(name);
    const contentBytes = bytes(content);
    const crc = crc32(contentBytes);
    const local = concat([
      u32(0x04034b50),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(contentBytes.length),
      u32(contentBytes.length),
      u16(nameBytes.length),
      u16(0),
      nameBytes,
      contentBytes
    ]);
    localParts.push(local);
    centralParts.push(
      concat([
        u32(0x02014b50),
        u16(20),
        u16(20),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(crc),
        u32(contentBytes.length),
        u32(contentBytes.length),
        u16(nameBytes.length),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(0),
        u32(offset),
        nameBytes
      ])
    );
    offset += local.length;
    index += 1;
  }
  const central = concat(centralParts);
  return concat([
    ...localParts,
    central,
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(index),
    u16(index),
    u32(central.length),
    u32(offset),
    u16(0)
  ]);
}

function crc32(data: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function columnName(index: number) {
  let name = '';
  while (index) {
    const remainder = (index - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    index = Math.floor((index - 1) / 26);
  }
  return name;
}

function escapeXml(value: string) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function bytes(value: string) {
  return new TextEncoder().encode(value);
}

function u16(value: number) {
  return new Uint8Array([value & 255, (value >> 8) & 255]);
}

function u32(value: number) {
  return new Uint8Array([value & 255, (value >> 8) & 255, (value >> 16) & 255, (value >> 24) & 255]);
}

function concat(parts: Uint8Array[]) {
  const out = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}
