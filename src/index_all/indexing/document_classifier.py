from __future__ import annotations

import unicodedata
from typing import Any, Literal, Mapping, Sequence


DocumentArchetype = Literal[
    "legislation_normative",
    "legislation_amending_act",
    "manual_procedural",
    "judicial_case",
    "spreadsheet_structured",
    "xml_structured",
    "financial_statement_ofx",
    "generic_document",
]

DOCUMENT_ARCHETYPES: tuple[DocumentArchetype, ...] = (
    "legislation_normative",
    "legislation_amending_act",
    "manual_procedural",
    "judicial_case",
    "spreadsheet_structured",
    "xml_structured",
    "financial_statement_ofx",
    "generic_document",
)

LEGAL_STRUCTURE_KINDS = {
    "preamble",
    "part",
    "book",
    "title",
    "chapter",
    "section",
    "subsection",
    "article",
    "legal_paragraph",
    "inciso",
    "alinea",
    "item",
}
SPREADSHEET_KINDS = {"sheet", "sheet_row", "table_header", "table_row"}
XML_KINDS = {"xml_node"}
OFX_KINDS = {"transaction"}

AMENDING_ACT_HINTS = (
    "altera a lei",
    "altera as leis",
    "altera o decreto",
    "altera os decretos",
    "acrescenta",
    "revoga",
    "renumera",
    "da nova redacao",
    "com as seguintes alteracoes",
    "passa a vigorar com a seguinte redacao",
)
MANUAL_HINTS = (
    "manual",
    "procedimento",
    "procedimentos",
    "instrucoes",
    "instrucao de trabalho",
    "guia",
    "passo a passo",
    "fluxo operacional",
    "rotina operacional",
)
JUDICIAL_CASE_HINTS = (
    "processo n",
    "autos n",
    "acordao",
    "sentenca",
    "decisao",
    "tribunal",
    "ementa",
    "relator",
    "apelacao",
    "agravo",
    "mandado de seguranca",
    "autor:",
    "reu:",
    "requerente",
    "requerido",
)


def _normalize_text(value: Any) -> str:
    compact = " ".join(str(value or "").split()).strip().lower()
    if not compact:
        return ""
    normalized = unicodedata.normalize("NFKD", compact)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _collect_search_text(
    metadata: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    parser_metadata: Mapping[str, Any],
    *,
    block_limit: int = 12,
) -> str:
    samples: list[str] = []

    for key in ("file_name", "file_stem", "source_path", "file_type"):
        normalized = _normalize_text(metadata.get(key))
        if normalized:
            samples.append(normalized)

    for key in ("mode", "root_tag"):
        normalized = _normalize_text(parser_metadata.get(key))
        if normalized:
            samples.append(normalized)

    for block in blocks[:block_limit]:
        for key in ("title", "text"):
            normalized = _normalize_text(block.get(key))
            if normalized:
                samples.append(normalized)

    return "\n".join(samples)


def _contains_any(text: str, hints: Sequence[str]) -> bool:
    return any(hint in text for hint in hints)


def _has_legal_structure(blocks: Sequence[Mapping[str, Any]], parser_metadata: Mapping[str, Any]) -> bool:
    mode = _normalize_text(parser_metadata.get("mode"))
    if mode == "structured_legal":
        return True
    return any(block.get("kind") in LEGAL_STRUCTURE_KINDS for block in blocks)


def classify_document_archetype(
    metadata: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    parser_metadata: Mapping[str, Any],
) -> DocumentArchetype:
    file_type = _normalize_text(metadata.get("file_type"))
    parser_mode = _normalize_text(parser_metadata.get("mode"))
    root_tag = _normalize_text(parser_metadata.get("root_tag"))
    block_kinds = {str(block.get("kind")) for block in blocks if block.get("kind")}
    search_text = _collect_search_text(metadata, blocks, parser_metadata)
    has_legal_structure = _has_legal_structure(blocks, parser_metadata)

    if (
        file_type == "ofx"
        or root_tag == "ofx"
        or bool(block_kinds & OFX_KINDS)
        or "transaction_count" in parser_metadata
    ):
        return "financial_statement_ofx"

    if has_legal_structure:
        if _contains_any(search_text, AMENDING_ACT_HINTS):
            return "legislation_amending_act"
        return "legislation_normative"

    if (
        file_type in {"csv", "xlsx"}
        or parser_mode in {"table_preview", "sheet_preview"}
        or bool(block_kinds & SPREADSHEET_KINDS)
    ):
        return "spreadsheet_structured"

    if (
        file_type == "xml"
        or parser_mode == "xml_tree"
        or root_tag
        or bool(block_kinds & XML_KINDS)
    ):
        return "xml_structured"

    if _contains_any(search_text, MANUAL_HINTS):
        return "manual_procedural"

    if _contains_any(search_text, JUDICIAL_CASE_HINTS):
        return "judicial_case"

    return "generic_document"
