from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    build_manual_blocks,
    looks_like_legal_document,
    looks_like_manual_document,
    normalize_text,
)


PDF_HEADER_RE = re.compile(r"^\d+\s+N[úu]mero\s+\d+\s*[–-]\s*\d{2}/\d{2}/\d{4}$", re.IGNORECASE)
PDF_PAGE_ONLY_RE = re.compile(r"^\d+$")
MANUAL_TITLE_HINTS = ("manual", "procedimento", "passo a passo", "guia")
MANUAL_STRUCTURE_HINTS = ("objetivos", "passos", "procedimento", "etapa", "etapas", "resumo")
MANUAL_OPERATION_HINTS = ("clique", "portal", "botão", "botao", "tela", "simulador")


def _is_ignorable_pdf_line(text: str) -> bool:
    return bool(PDF_HEADER_RE.match(text) or PDF_PAGE_ONLY_RE.match(text))


def _extract_page_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        cleaned = normalize_text(raw_line)
        if not cleaned or _is_ignorable_pdf_line(cleaned):
            continue
        lines.append((line_number, cleaned))
    return lines


def _extract_records(page_texts: list[str]) -> list[StructuredTextRecord]:
    records: list[StructuredTextRecord] = []
    for page_idx, text in enumerate(page_texts, start=1):
        for line_number, line in _extract_page_lines(text):
            records.append(
                StructuredTextRecord(
                    text=line,
                    locator={
                        "page": page_idx,
                        "sheet": None,
                        "line_start": line_number,
                        "line_end": line_number,
                    },
                    extra={"page": page_idx},
                )
            )
    return records


def _build_page_blocks(page_texts: list[str]) -> list[dict]:
    blocks = []
    block_idx = 1

    for page_idx, text in enumerate(page_texts, start=1):
        cleaned = text.strip()
        if not cleaned:
            continue

        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "page_text",
                "title": f"Page {page_idx}",
                "text": cleaned,
                "locator": {"page": page_idx, "sheet": None, "line_start": None, "line_end": None},
                "extra": {},
            }
        )
        block_idx += 1

    return blocks


def _should_prefer_manual(record_texts: list[str]) -> bool:
    early_text = " ".join(normalize_text(text).lower() for text in record_texts[:10])
    title_hits = sum(1 for hint in MANUAL_TITLE_HINTS if hint in early_text)
    structure_hits = sum(1 for hint in MANUAL_STRUCTURE_HINTS if hint in early_text)
    operation_hits = sum(1 for hint in MANUAL_OPERATION_HINTS if hint in early_text)
    return title_hits >= 1 or structure_hits >= 2 or (structure_hits >= 1 and operation_hits >= 2)


def build_blocks_from_page_texts(page_texts: list[str]) -> tuple[list[dict], str]:
    records = _extract_records(page_texts)
    record_texts = [record.text for record in records]
    is_manual_document = looks_like_manual_document(record_texts)
    is_legal_document = looks_like_legal_document(record_texts)
    if is_manual_document and (not is_legal_document or _should_prefer_manual(record_texts)):
        return build_manual_blocks(records), "structured_manual"
    if is_legal_document:
        return build_legal_blocks(records), "structured_legal"
    return _build_page_blocks(page_texts), "page_text"


def parse_pdf(path: Path) -> dict:
    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "") for page in reader.pages]
    blocks, mode = build_blocks_from_page_texts(page_texts)

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "page_count": len(reader.pages),
                "block_count": len(blocks),
                "mode": mode,
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
