from __future__ import annotations

from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    looks_like_legal_document,
    make_preview_title,
    normalize_text,
)


def _extract_records(root: ET.Element) -> list[StructuredTextRecord]:
    records: list[StructuredTextRecord] = []
    line_number = 1

    for elem in root.iter():
        text = normalize_text(elem.text or "")
        if text:
            records.append(
                StructuredTextRecord(
                    text=text,
                    locator={"page": None, "sheet": None, "line_start": line_number, "line_end": line_number},
                    extra={"tag": elem.tag, "attributes": dict(elem.attrib)},
                )
            )
            line_number += 1

        tail = normalize_text(elem.tail or "")
        if tail:
            records.append(
                StructuredTextRecord(
                    text=tail,
                    locator={"page": None, "sheet": None, "line_start": line_number, "line_end": line_number},
                    extra={"tag": f"{elem.tag}:tail"},
                )
            )
            line_number += 1

    return records


def _build_fallback_blocks(records: list[StructuredTextRecord]) -> list[dict]:
    return [
        {
            "id": f"block_{idx:04d}",
            "kind": "xml_node",
            "title": record.extra.get("tag"),
            "text": record.text,
            "locator": dict(record.locator),
            "extra": dict(record.extra),
        }
        for idx, record in enumerate(records, start=1)
    ]


def parse_xml(path: Path) -> dict:
    root = ET.parse(path).getroot()
    records = _extract_records(root)

    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = _build_fallback_blocks(records)
        mode = "xml_tree"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "root_tag": root.tag,
                "node_count": len(records),
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
