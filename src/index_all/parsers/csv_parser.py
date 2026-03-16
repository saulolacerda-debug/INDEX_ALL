from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    looks_like_legal_document,
    make_preview_title,
    normalize_text,
)


def _render_row(row: list[str]) -> str:
    values = [str(cell) for cell in row if cell is not None and str(cell).strip()]
    if not values:
        return ""
    return normalize_text(" | ".join(values))


def parse_csv(path: Path) -> dict:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as file_obj:
        reader = csv.reader(file_obj)
        rows = [list(row) for row in reader]

    records = [
        StructuredTextRecord(
            text=rendered,
            locator={"page": None, "sheet": None, "line_start": idx, "line_end": idx},
            extra={"values": row},
        )
        for idx, row in enumerate(rows, start=1)
        if (rendered := _render_row(row))
    ]

    header_present = False
    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = []
        if rows:
            header = rows[0]
            rendered_header = _render_row(header)
            if rendered_header:
                blocks.append(
                    {
                        "id": "block_0001",
                        "kind": "table_header",
                        "title": "Header",
                        "text": rendered_header,
                        "locator": {"page": None, "sheet": None, "line_start": 1, "line_end": 1},
                        "extra": {"columns": header},
                    }
                )
                header_present = True

        block_idx = len(blocks) + 1
        for row_number, row in enumerate(rows[1:], start=2):
            rendered = _render_row(row)
            if not rendered:
                continue
            blocks.append(
                {
                    "id": f"block_{block_idx:04d}",
                    "kind": "table_row",
                    "title": make_preview_title(rendered),
                    "text": rendered,
                    "locator": {"page": None, "sheet": None, "line_start": row_number, "line_end": row_number},
                    "extra": {"values": row},
                }
            )
            block_idx += 1
        mode = "table_full"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "row_count": len(rows),
                "non_empty_row_count": len(records),
                "data_row_count": max(len(records) - 1, 0) if header_present else len(records),
                "column_count": max((len(row) for row in rows), default=0),
                "header_present": header_present,
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
