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
    return normalize_text(" | ".join(cell for cell in row if cell is not None))


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

    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = []
        if rows:
            header = rows[0]
            blocks.append(
                {
                    "id": "block_0001",
                    "kind": "table_header",
                    "title": "Header",
                    "text": _render_row(header),
                    "locator": {"page": None, "sheet": None, "line_start": 1, "line_end": 1},
                    "extra": {"columns": header},
                }
            )

        for idx, row in enumerate(rows[1:21], start=2):
            blocks.append(
                {
                    "id": f"block_{idx:04d}",
                    "kind": "table_row",
                    "title": make_preview_title(_render_row(row)),
                    "text": _render_row(row),
                    "locator": {"page": None, "sheet": None, "line_start": idx, "line_end": idx},
                    "extra": {"values": row},
                }
            )
        mode = "table_preview"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "row_count": len(rows),
                "column_count": max((len(row) for row in rows), default=0),
                "preview_limit": min(max(len(rows) - 1, 0), 20),
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
