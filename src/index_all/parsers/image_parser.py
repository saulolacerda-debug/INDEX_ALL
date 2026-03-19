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
from index_all.parsers.ocr_service import extract_image_ocr


def parse_image(path: Path) -> dict:
    ocr_payload = extract_image_ocr(path)
    ocr_lines = list(ocr_payload.get("lines", []) or [])

    records = [
        StructuredTextRecord(
            text=cleaned,
            locator={
                "page": int(line.get("page_number") or 1),
                "sheet": None,
                "line_start": int(line.get("line_number") or line_index),
                "line_end": int(line.get("line_number") or line_index),
            },
            extra={
                "confidence": line.get("confidence"),
                "bounding_box": line.get("bounding_box"),
                "ocr_provider": ocr_payload.get("provider"),
            },
        )
        for line_index, line in enumerate(ocr_lines, start=1)
        if (cleaned := normalize_text(str(line.get("text") or "")))
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
                "extra": dict(record.extra),
            }
            for idx, record in enumerate(records, start=1)
        ]
        mode = "ocr_image"

    confidences = [record.extra.get("confidence") for record in records if record.extra.get("confidence") is not None]
    parser_metadata = {
        "mode": mode,
        "image_format": path.suffix.lower().lstrip("."),
        "ocr_provider": ocr_payload.get("provider"),
        "ocr_engine": ocr_payload.get("engine"),
        "ocr_language_hint": ocr_payload.get("language_hint"),
        "ocr_attempted_providers": ocr_payload.get("attempted_providers", []),
        "ocr_line_count": len(records),
        "ocr_page_count": ocr_payload.get("page_count", 1),
        "ocr_average_confidence": ocr_payload.get("average_confidence"),
        "ocr_text_found": bool(records),
        "block_count": len(blocks),
        "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
    }
    if confidences:
        parser_metadata["ocr_confident_line_count"] = len(confidences)

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": parser_metadata,
        }
    }
