from __future__ import annotations

from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    looks_like_legal_document,
    make_preview_title,
    normalize_text,
)


HTML_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li")


def _extract_records(soup: BeautifulSoup) -> tuple[list[StructuredTextRecord], str | None]:
    records: list[StructuredTextRecord] = []
    title_text = normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if title_text:
        records.append(
            StructuredTextRecord(
                text=title_text,
                locator={"page": None, "sheet": None, "line_start": 1, "line_end": 1},
                extra={"tag": "title"},
                style_name="h1",
            )
        )

    line_number = 2 if title_text else 1
    nodes = soup.find_all(HTML_TEXT_TAGS)
    if not nodes:
        body = soup.body or soup
        for text in body.stripped_strings:
            cleaned = normalize_text(text)
            if not cleaned:
                continue
            records.append(
                StructuredTextRecord(
                    text=cleaned,
                    locator={"page": None, "sheet": None, "line_start": line_number, "line_end": line_number},
                    extra={"tag": "text"},
                )
            )
            line_number += 1
        return records, title_text or None

    for node in nodes:
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        records.append(
            StructuredTextRecord(
                text=text,
                locator={"page": None, "sheet": None, "line_start": line_number, "line_end": line_number},
                extra={"tag": node.name},
                style_name=node.name,
            )
        )
        line_number += 1

    return records, title_text or None


def _build_fallback_blocks(records: list[StructuredTextRecord]) -> list[dict]:
    blocks = []
    for idx, record in enumerate(records, start=1):
        tag_name = record.extra.get("tag")
        if isinstance(tag_name, str) and tag_name.lower().startswith("h") and tag_name[1:].isdigit():
            blocks.append(
                {
                    "id": f"block_{idx:04d}",
                    "kind": "heading",
                    "title": make_preview_title(record.text, max_length=120),
                    "text": record.text,
                    "locator": dict(record.locator),
                    "extra": {"tag": tag_name, "heading_level": int(tag_name[1:])},
                }
            )
            continue

        blocks.append(
            {
                "id": f"block_{idx:04d}",
                "kind": "list_item" if tag_name == "li" else "paragraph",
                "title": make_preview_title(record.text),
                "text": record.text,
                "locator": dict(record.locator),
                "extra": dict(record.extra),
            }
        )
    return blocks


def parse_html(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    records, title_text = _extract_records(soup)

    if looks_like_legal_document([record.text for record in records]):
        blocks = build_legal_blocks(records)
        mode = "structured_legal"
    else:
        blocks = _build_fallback_blocks(records)
        mode = "structured_html"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "has_title": bool(title_text),
                "mode": mode,
                "block_count": len(blocks),
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
