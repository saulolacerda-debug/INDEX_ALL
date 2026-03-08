from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    looks_like_legal_document,
    make_preview_title,
    normalize_text,
)


def _render_values(values: list[object]) -> str:
    return normalize_text(" | ".join("" if value is None else str(value) for value in values))


def parse_xlsx(path: Path) -> dict:
    workbook = load_workbook(filename=str(path), data_only=True)

    records: list[StructuredTextRecord] = []
    for sheet in workbook.worksheets:
        max_row = sheet.max_row or 0
        max_column = sheet.max_column or 0
        for row_number in range(1, max_row + 1):
            values = [sheet.cell(row=row_number, column=col).value for col in range(1, max_column + 1)]
            rendered = _render_values(values)
            if not rendered:
                continue
            records.append(
                StructuredTextRecord(
                    text=rendered,
                    locator={"page": None, "sheet": sheet.title, "line_start": row_number, "line_end": row_number},
                    extra={"sheet": sheet.title, "values": values},
                )
            )

    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = []
        block_idx = 1

        for sheet in workbook.worksheets:
            max_row = sheet.max_row or 0
            max_column = sheet.max_column or 0
            blocks.append(
                {
                    "id": f"block_{block_idx:04d}",
                    "kind": "sheet",
                    "title": sheet.title,
                    "text": f"Sheet {sheet.title}",
                    "locator": {"page": None, "sheet": sheet.title, "line_start": None, "line_end": None},
                    "extra": {"max_row": max_row, "max_column": max_column},
                }
            )
            block_idx += 1

            preview_limit = min(max_row, 10)
            for row_number in range(1, preview_limit + 1):
                values = [sheet.cell(row=row_number, column=col).value for col in range(1, max_column + 1)]
                rendered = _render_values(values)
                blocks.append(
                    {
                        "id": f"block_{block_idx:04d}",
                        "kind": "sheet_row",
                        "title": make_preview_title(rendered),
                        "text": rendered,
                        "locator": {"page": None, "sheet": sheet.title, "line_start": row_number, "line_end": row_number},
                        "extra": {"values": values},
                    }
                )
                block_idx += 1
        mode = "sheet_preview"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "sheet_names": workbook.sheetnames,
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
