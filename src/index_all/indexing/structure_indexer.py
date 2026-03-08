from __future__ import annotations

import re

from index_all.indexing.document_classifier import DocumentArchetype
from index_all.parsers.legal_structure import text_indicates_amendment_context


STRUCTURE_LEVELS = {
    "preamble": 1,
    "part": 2,
    "book": 3,
    "title": 4,
    "chapter": 5,
    "section": 6,
    "subsection": 7,
    "article": 8,
    "legal_paragraph": 9,
    "inciso": 10,
    "alinea": 11,
    "item": 12,
}
EMBEDDED_AMENDING_LEVELS = {
    "part": 9,
    "book": 10,
    "title": 11,
    "chapter": 12,
    "section": 13,
    "subsection": 14,
    "article": 15,
    "legal_paragraph": 16,
    "inciso": 17,
    "alinea": 18,
    "item": 19,
}
LEGAL_ARCHETYPES = {"legislation_normative", "legislation_amending_act"}
NON_HIERARCHICAL_ARCHETYPES = {"spreadsheet_structured", "xml_structured", "financial_statement_ofx"}
STRUCTURAL_HEADING_KINDS = {"part", "book", "title", "chapter", "section", "subsection"}
ARTICLE_NUMBER_RE = re.compile(r"Art\.\s*(?P<number>\d+)", re.IGNORECASE)


def _entry_title(block: dict, fallback_index: int) -> str:
    text = (block.get("text") or "").strip()
    extra = block.get("extra", {})
    return (
        extra.get("index_title")
        or extra.get("display_title")
        or block.get("title")
        or (text[:80] if text else f"Block {fallback_index}")
    )


def _make_entry(block: dict, index: int) -> dict:
    return {
        "id": f"idx_{index:04d}",
        "title": _entry_title(block, index),
        "kind": block.get("kind"),
        "locator": block.get("locator", {}),
        "level": None,
        "parent_id": None,
        "children": [],
    }


def _append_entry(
    hierarchical_entries: list[dict],
    stack: list[tuple[int, dict]],
    entry: dict,
    *,
    level: int,
) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()

    entry["level"] = level
    if stack:
        entry["parent_id"] = stack[-1][1]["id"]
        stack[-1][1]["children"].append(entry)
    else:
        entry["parent_id"] = None
        hierarchical_entries.append(entry)

    stack.append((level, entry))


def _build_flat_fallback(blocks: list[dict]) -> list[dict]:
    entries = [_make_entry(block, idx) for idx, block in enumerate(blocks, start=1)]
    for entry in entries:
        entry["level"] = 1
        entry["parent_id"] = None
    return entries


def _build_normative_index(blocks: list[dict]) -> list[dict]:
    hierarchical_entries: list[dict] = []
    stack: list[tuple[int, dict]] = []
    structural_count = 0

    for idx, block in enumerate(blocks, start=1):
        kind = block.get("kind")
        level = STRUCTURE_LEVELS.get(kind)
        if level is None:
            continue

        structural_count += 1
        entry = _make_entry(block, idx)
        if kind == "preamble":
            entry["level"] = STRUCTURE_LEVELS["preamble"]
            entry["parent_id"] = None
            hierarchical_entries.append(entry)
            continue

        _append_entry(hierarchical_entries, stack, entry, level=level)

    if structural_count:
        return hierarchical_entries
    return _build_flat_fallback(blocks)


def _extract_article_number(block: dict) -> int | None:
    value = str(block.get("title") or block.get("text") or "")
    match = ARTICLE_NUMBER_RE.search(value)
    if not match:
        return None
    return int(match.group("number"))


def _amending_article_is_embedded(
    block: dict,
    *,
    current_act_article_number: int | None,
    amendment_context_active: bool,
) -> bool:
    if not amendment_context_active:
        return False

    if block.get("extra", {}).get("starts_with_quote"):
        return True

    article_number = _extract_article_number(block)
    if article_number is None or current_act_article_number is None:
        return False

    return article_number > current_act_article_number + 1


def _block_opens_amendment_context(block: dict) -> bool:
    if block.get("extra", {}).get("amendment_context"):
        return True
    return text_indicates_amendment_context(str(block.get("text") or ""))


def _build_amending_act_index(blocks: list[dict]) -> list[dict]:
    hierarchical_entries: list[dict] = []
    stack: list[tuple[int, dict]] = []
    structural_count = 0

    current_act_article_title: str | None = None
    current_act_article_number: int | None = None
    amendment_context_active = False
    embedded_scope_active = False

    for idx, block in enumerate(blocks, start=1):
        kind = block.get("kind")
        base_level = STRUCTURE_LEVELS.get(kind)
        if base_level is None:
            continue

        structural_count += 1
        entry = _make_entry(block, idx)

        if kind == "preamble":
            entry["level"] = STRUCTURE_LEVELS["preamble"]
            entry["parent_id"] = None
            hierarchical_entries.append(entry)
            current_act_article_title = None
            current_act_article_number = None
            amendment_context_active = False
            embedded_scope_active = False
            continue

        if kind in STRUCTURAL_HEADING_KINDS and not amendment_context_active:
            current_act_article_title = None
            current_act_article_number = None
            amendment_context_active = False
            embedded_scope_active = False
            _append_entry(hierarchical_entries, stack, entry, level=base_level)
            continue

        if kind == "article":
            is_embedded_article = _amending_article_is_embedded(
                block,
                current_act_article_number=current_act_article_number,
                amendment_context_active=amendment_context_active,
            )
            effective_level = EMBEDDED_AMENDING_LEVELS["article"] if is_embedded_article else base_level
            _append_entry(hierarchical_entries, stack, entry, level=effective_level)

            if is_embedded_article:
                embedded_scope_active = True
                continue

            current_act_article_title = block.get("title")
            current_act_article_number = _extract_article_number(block)
            amendment_context_active = _block_opens_amendment_context(block)
            embedded_scope_active = False
            continue

        effective_level = base_level
        locator_article = (block.get("locator") or {}).get("article")
        is_embedded_child = False
        if amendment_context_active and current_act_article_title:
            if kind in STRUCTURAL_HEADING_KINDS:
                is_embedded_child = True
            elif locator_article and locator_article != current_act_article_title:
                is_embedded_child = True
            elif embedded_scope_active:
                is_embedded_child = True

        if is_embedded_child:
            effective_level = EMBEDDED_AMENDING_LEVELS.get(kind, base_level)

        _append_entry(hierarchical_entries, stack, entry, level=effective_level)

        if kind in STRUCTURAL_HEADING_KINDS and is_embedded_child:
            embedded_scope_active = True

        if current_act_article_title and not embedded_scope_active and _block_opens_amendment_context(block):
            amendment_context_active = True

    if structural_count:
        return hierarchical_entries
    return _build_flat_fallback(blocks)


def _manual_entry_level(block: dict) -> int | None:
    if block.get("kind") != "heading":
        return None

    heading_level = block.get("extra", {}).get("heading_level")
    if isinstance(heading_level, int):
        return max(1, min(heading_level, 6))
    return 1


def _build_manual_index(blocks: list[dict]) -> list[dict]:
    hierarchical_entries: list[dict] = []
    stack: list[tuple[int, dict]] = []
    structural_count = 0

    for idx, block in enumerate(blocks, start=1):
        level = _manual_entry_level(block)
        if level is None:
            continue

        structural_count += 1
        entry = _make_entry(block, idx)
        _append_entry(hierarchical_entries, stack, entry, level=level)

    if structural_count:
        return hierarchical_entries
    return _build_flat_fallback(blocks)


def build_structure_index(blocks: list[dict], document_archetype: DocumentArchetype) -> list[dict]:
    if document_archetype == "legislation_normative":
        return _build_normative_index(blocks)

    if document_archetype == "legislation_amending_act":
        return _build_amending_act_index(blocks)

    if document_archetype == "manual_procedural":
        return _build_manual_index(blocks)

    if document_archetype in NON_HIERARCHICAL_ARCHETYPES:
        return _build_flat_fallback(blocks)

    return _build_flat_fallback(blocks)
