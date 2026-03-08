from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterator

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    build_manual_blocks,
    build_locator,
    classify_paragraph,
    looks_like_legal_document,
    looks_like_manual_document,
    new_structure_context,
    normalize_text,
    update_context,
)


def _iter_block_items(document: DocxDocument) -> Iterator[Paragraph | Table]:
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _build_table_block(table: Table, position: int, table_count: int) -> dict:
    row_texts = []
    for row in table.rows:
        row_texts.append(" | ".join(normalize_text(cell.text) for cell in row.cells))

    return {
        "id": "",
        "kind": "table",
        "title": f"Tabela {table_count}",
        "text": "\n".join(row_texts),
        "locator": {"page": None, "sheet": None, "line_start": position, "line_end": position},
        "extra": {"rows": len(table.rows)},
    }


def _assign_block_ids(blocks: list[dict]) -> list[dict]:
    for index, block in enumerate(blocks, start=1):
        block["id"] = f"block_{index:04d}"
    return blocks


def _sort_blocks_in_document_order(blocks: list[dict]) -> list[dict]:
    def order_key(block: dict) -> tuple[int, int]:
        locator = block.get("locator", {})
        line_start = locator.get("line_start")
        return (line_start is None, line_start or 0)

    return sorted(blocks, key=order_key)


def parse_docx(path: Path) -> dict:
    document = Document(str(path))
    items = list(_iter_block_items(document))
    paragraph_texts = [
        normalize_text(item.text or "")
        for item in items
        if isinstance(item, Paragraph) and normalize_text(item.text or "")
    ]
    is_legal_document = looks_like_legal_document(paragraph_texts)
    is_manual_document = not is_legal_document and looks_like_manual_document(paragraph_texts)

    paragraph_count = 0
    table_count = 0

    if is_legal_document or is_manual_document:
        records: list[StructuredTextRecord] = []
        trailing_table_blocks: list[dict] = []

        for position, item in enumerate(items, start=1):
            if isinstance(item, Paragraph):
                text = normalize_text(item.text or "")
                if not text:
                    continue
                paragraph_count += 1
                style_name = item.style.name if item.style else None
                records.append(
                    StructuredTextRecord(
                        text=text,
                        locator={"page": None, "sheet": None, "line_start": position, "line_end": position},
                        extra={"style": style_name},
                        style_name=style_name,
                    )
                )
                continue

            table_count += 1
            trailing_table_blocks.append(_build_table_block(item, position, table_count))

        if is_legal_document:
            blocks = build_legal_blocks(records)
            mode = "structured_legal"
        else:
            blocks = build_manual_blocks(records)
            mode = "structured_manual"
        blocks = _sort_blocks_in_document_order(blocks + trailing_table_blocks)
        blocks = _assign_block_ids(blocks)
    else:
        blocks = []
        block_idx = 1
        context = new_structure_context()

        for position, item in enumerate(items, start=1):
            if isinstance(item, Paragraph):
                text = normalize_text(item.text or "")
                if not text:
                    continue

                paragraph_count += 1
                style_name = item.style.name if item.style else None
                continuation_text = None
                for next_item in items[position:]:
                    if isinstance(next_item, Paragraph):
                        candidate = normalize_text(next_item.text or "")
                        if candidate:
                            continuation_text = candidate
                            break

                classification = classify_paragraph(
                    text,
                    style_name=style_name,
                    continuation_text=continuation_text,
                    context=context,
                )
                update_context(context, classification)

                extra = {"style": style_name}
                if classification.label:
                    extra["label"] = classification.label
                if classification.heading_level is not None:
                    extra["heading_level"] = classification.heading_level

                blocks.append(
                    {
                        "id": f"block_{block_idx:04d}",
                        "kind": classification.kind,
                        "title": classification.title,
                        "text": text,
                        "locator": build_locator(context, line_start=position, line_end=position),
                        "extra": extra,
                    }
                )
                block_idx += 1
                continue

            table_count += 1
            blocks.append(_build_table_block(item, position, table_count))
            block_idx += 1

        blocks = _assign_block_ids(blocks)
        mode = "document_blocks"

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "paragraph_count": paragraph_count,
                "table_count": table_count,
                "block_count": len(blocks),
                "mode": mode,
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
