from __future__ import annotations

import unicodedata
from collections import Counter
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

CORE_AMENDING_ACT_HINTS = (
    "passa a vigorar com as seguintes alteracoes",
    "passam a vigorar com as seguintes alteracoes",
    "ficam alterados os seguintes dispositivos",
    "fica alterado o seguinte dispositivo",
    "a constituicao federal passa a vigorar com as seguintes alteracoes",
    "com a seguinte redacao",
    "com as seguintes alteracoes",
)
AMENDING_ACT_HINTS = (
    *CORE_AMENDING_ACT_HINTS,
    "altera a lei",
    "altera as leis",
    "altera o decreto",
    "altera os decretos",
    "acrescenta",
    "revoga",
    "renumera",
    "da nova redacao",
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
MANUAL_OPERATIONAL_HINTS = (
    "objetivo",
    "objetivos",
    "introducao",
    "passos",
    "etapa",
    "etapas",
    "procedimento",
    "procedimentos",
    "resumo",
    "tela",
    "telas",
    "botao",
    "clique",
    "portal",
    "sistema",
    "acessar",
    "preencher",
    "validar",
    "enviar",
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


def _count_text_hits(text: str, hints: Sequence[str]) -> int:
    return sum(1 for hint in hints if hint in text)


def _has_legal_structure(blocks: Sequence[Mapping[str, Any]], parser_metadata: Mapping[str, Any]) -> bool:
    mode = _normalize_text(parser_metadata.get("mode"))
    if mode == "structured_legal":
        return True
    return any(block.get("kind") in LEGAL_STRUCTURE_KINDS for block in blocks)


def _legal_block_counts(blocks: Sequence[Mapping[str, Any]]) -> Counter[str]:
    return Counter(str(block.get("kind")) for block in blocks if block.get("kind"))


def _classify_legal_archetype(
    metadata: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    parser_metadata: Mapping[str, Any],
) -> DocumentArchetype:
    search_text = _collect_search_text(metadata, blocks, parser_metadata, block_limit=12)
    early_text = _collect_search_text(metadata, blocks, parser_metadata, block_limit=5)
    file_name = _normalize_text(metadata.get("file_name"))
    file_stem = _normalize_text(metadata.get("file_stem"))
    file_title_text = " ".join(part for part in (file_name, file_stem) if part)
    block_counts = _legal_block_counts(blocks)

    structural_headings = sum(block_counts[kind] for kind in ("part", "book", "title", "chapter", "section", "subsection"))
    major_normative_structure = sum(block_counts[kind] for kind in ("part", "book", "title", "chapter", "section", "subsection", "article"))
    article_count = block_counts["article"]

    normative_score = 0
    if parser_metadata.get("mode") == "structured_legal":
        normative_score += 1
    if block_counts["preamble"]:
        normative_score += 1
    if structural_headings >= 2:
        normative_score += 3
    if structural_headings >= 4:
        normative_score += 2
    if article_count >= 3:
        normative_score += 1
    if article_count >= 8:
        normative_score += 1
    if major_normative_structure >= 6:
        normative_score += 1
    if "lei complementar" in file_title_text or "lei ordinaria" in file_title_text or "codigo" in file_title_text:
        normative_score += 1

    amending_score = _count_text_hits(search_text, AMENDING_ACT_HINTS)
    amending_score += 2 * _count_text_hits(early_text, CORE_AMENDING_ACT_HINTS)
    if "emenda constitucional" in file_title_text:
        amending_score += 3
    if "altera" in file_title_text or "alteracoes" in file_title_text:
        amending_score += 1

    if structural_headings >= 2:
        amending_score = max(amending_score - 1, 0)
    if structural_headings >= 4:
        amending_score = max(amending_score - 1, 0)

    if amending_score >= max(3, normative_score + 1):
        return "legislation_amending_act"
    return "legislation_normative"


def _looks_like_manual_document(
    metadata: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    parser_metadata: Mapping[str, Any],
) -> bool:
    parser_mode = _normalize_text(parser_metadata.get("mode"))
    if parser_mode == "structured_manual":
        return True

    search_text = _collect_search_text(metadata, blocks, parser_metadata, block_limit=14)
    block_kinds = {str(block.get("kind")) for block in blocks if block.get("kind")}
    heading_count = sum(1 for block in blocks if block.get("kind") == "heading")
    manual_hits = _count_text_hits(search_text, MANUAL_HINTS)
    operational_hits = _count_text_hits(search_text, MANUAL_OPERATIONAL_HINTS)

    if manual_hits >= 2:
        return True
    if manual_hits >= 1 and operational_hits >= 2:
        return True
    if heading_count >= 2 and operational_hits >= 3 and "page_text" not in block_kinds:
        return True
    return False


def classify_document_archetype(
    metadata: Mapping[str, Any],
    blocks: Sequence[Mapping[str, Any]],
    parser_metadata: Mapping[str, Any],
) -> DocumentArchetype:
    file_type = _normalize_text(metadata.get("file_type"))
    parser_mode = _normalize_text(parser_metadata.get("mode"))
    root_tag = _normalize_text(parser_metadata.get("root_tag"))
    block_kinds = {str(block.get("kind")) for block in blocks if block.get("kind")}
    has_legal_structure = _has_legal_structure(blocks, parser_metadata)
    search_text = _collect_search_text(metadata, blocks, parser_metadata)

    if (
        file_type == "ofx"
        or root_tag == "ofx"
        or bool(block_kinds & OFX_KINDS)
        or "transaction_count" in parser_metadata
    ):
        return "financial_statement_ofx"

    if has_legal_structure:
        return _classify_legal_archetype(metadata, blocks, parser_metadata)

    if _looks_like_manual_document(metadata, blocks, parser_metadata):
        return "manual_procedural"

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

    if _contains_any(search_text, JUDICIAL_CASE_HINTS):
        return "judicial_case"

    return "generic_document"
