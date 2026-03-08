from __future__ import annotations

from index_all.indexing.document_classifier import DocumentArchetype


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
LEGAL_ARCHETYPES = {"legislation_normative", "legislation_amending_act"}
NON_HIERARCHICAL_ARCHETYPES = {"spreadsheet_structured", "xml_structured", "financial_statement_ofx"}


def _entry_title(block: dict, fallback_index: int) -> str:
    text = (block.get("text") or "").strip()
    extra = block.get("extra", {})
    return (
        extra.get("index_title")
        or extra.get("display_title")
        or block.get("title")
        or (text[:80] if text else f"Block {fallback_index}")
    )


def _entry_level(block: dict, document_archetype: DocumentArchetype) -> int | None:
    kind = block.get("kind")
    if kind == "heading":
        heading_level = block.get("extra", {}).get("heading_level")
        if isinstance(heading_level, int):
            return max(1, heading_level)
        return 1

    if document_archetype in NON_HIERARCHICAL_ARCHETYPES:
        return None

    if document_archetype in LEGAL_ARCHETYPES:
        return STRUCTURE_LEVELS.get(kind)

    return None


def _make_entry(block: dict, index: int) -> dict:
    return {
        "id": f"idx_{index:04d}",
        "title": _entry_title(block, index),
        "kind": block.get("kind"),
        "locator": block.get("locator", {}),
        "children": [],
    }


def build_structure_index(blocks: list[dict], document_archetype: DocumentArchetype) -> list[dict]:
    hierarchical_entries: list[dict] = []
    stack: list[tuple[int, dict]] = []
    structural_count = 0

    for idx, block in enumerate(blocks, start=1):
        level = _entry_level(block, document_archetype)
        if level is None:
            continue

        structural_count += 1
        entry = _make_entry(block, idx)
        if block.get("kind") == "preamble":
            hierarchical_entries.append(entry)
            continue

        while stack and stack[-1][0] >= level:
            stack.pop()

        if stack:
            stack[-1][1]["children"].append(entry)
        else:
            hierarchical_entries.append(entry)

        stack.append((level, entry))

    if structural_count:
        return hierarchical_entries

    return [_make_entry(block, idx) for idx, block in enumerate(blocks, start=1)]
