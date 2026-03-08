from __future__ import annotations

from collections import Counter
from pathlib import Path

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    looks_like_legal_document,
    make_preview_title,
    normalize_text,
)


def parse_txt(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    records = [
        StructuredTextRecord(
            text=cleaned,
            locator={"page": None, "sheet": None, "line_start": idx, "line_end": idx},
            extra={},
        )
        for idx, line in enumerate(lines, start=1)
        if (cleaned := normalize_text(line))
    ]

    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = [
            {
                "id": f"block_{idx:04d}",
                "kind": "line",
                "title": make_preview_title(record.text),
                "text": record.text,
                "locator": dict(record.locator),
                "extra": {},
            }
            for idx, record in enumerate(records, start=1)
        ]
        mode = "line_text"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "line_count": len(lines),
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
