
#!/usr/bin/env python3
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any

NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def read_shared_strings(xml_content: bytes) -> List[str]:
    root = ET.fromstring(xml_content)
    strings = []
    for si in root.findall('.//main:si', NS):
        t = si.find('./main:t', NS)
        if t is not None and t.text:
            strings.append(t.text)
        else:
            # Check for rich text (multiple <r> elements)
            parts = []
            for r in si.findall('./main:r', NS):
                t = r.find('./main:t', NS)
                if t is not None and t.text:
                    parts.append(t.text)
            strings.append(''.join(parts))
    return strings


def read_sheet(xml_content: bytes, shared_strings: List[str]) -> List[List[str]]:
    root = ET.fromstring(xml_content)
    sheet_data = root.find('./main:sheetData', NS)
    if sheet_data is None:
        return []

    rows = []
    for row in sheet_data.findall('./main:row', NS):
        row_cells = []
        for c in row.findall('./main:c', NS):
            cell_type = c.get('t', '')
            v = c.find('./main:v', NS)

            if v is not None and v.text:
                if cell_type == 's':
                    # Shared string
                    idx = int(v.text)
                    if idx &lt; len(shared_strings):
                        row_cells.append(shared_strings[idx])
                    else:
                        row_cells.append('')
                else:
                    # Other types (number, etc.)
                    row_cells.append(v.text)
            else:
                row_cells.append('')
        rows.append(row_cells)
    return rows


def main():
    xlsx_path = Path('/home/tuo/project/contact_db/external_data/KolClaw达人标签&amp;沟通话术.xlsx')

    with zipfile.ZipFile(xlsx_path, 'r') as zf:
        # Read shared strings
        shared_strings = read_shared_strings(zf.read('xl/sharedStrings.xml'))

        # Read workbook to get sheet names and relationships
        workbook_xml = zf.read('xl/workbook.xml')
        workbook_root = ET.fromstring(workbook_xml)

        # Get sheet info
        sheets_info = []
        for sheet in workbook_root.findall('.//main:sheet', NS):
            sheets_info.append({
                'name': sheet.get('name'),
                'sheet_id': sheet.get('sheetId'),
                'r_id': sheet.get(f'{{{NS["r"]}}}id'),
            })

        # Read workbook relationships to map r_id to file paths
        rels_xml = zf.read('xl/_rels/workbook.xml.rels')
        rels_root = ET.fromstring(rels_xml)
        rel_map = {}
        for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
            rel_map[rel.get('Id')] = rel.get('Target')

        # Read each sheet
        for sheet_info in sheets_info:
            r_id = sheet_info['r_id']
            target = rel_map.get(r_id)
            if target and target.startswith('worksheets/'):
                sheet_path = f'xl/{target}'
                sheet_xml = zf.read(sheet_path)
                sheet_data = read_sheet(sheet_xml, shared_strings)

                print('=' * 80)
                print(f"Sheet: {sheet_info['name']}")
                print('=' * 80)
                print()
                for i, row in enumerate(sheet_data[:30]):  # Show first 30 rows
                    print(f"Row {i+1}: {row}")
                print()
                print(f"Total rows: {len(sheet_data)}")
                print()


if __name__ == '__main__':
    main()

