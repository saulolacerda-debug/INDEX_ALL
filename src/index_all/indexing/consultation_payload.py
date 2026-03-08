from __future__ import annotations

from collections import Counter

from index_all.indexing.document_classifier import DocumentArchetype


LOCATOR_KEYS = ("part", "book", "title", "chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item")
STRUCTURE_KIND_ORDER = (
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
)


def format_locator_path(locator: dict) -> str | None:
    parts = [str(locator.get(key)) for key in LOCATOR_KEYS if locator.get(key)]
    if not parts:
        return None
    return " > ".join(parts)


def extract_hierarchy_path(locator: dict) -> list[str]:
    return [str(locator.get(key)) for key in LOCATOR_KEYS if locator.get(key)]


def format_position(locator: dict) -> str | None:
    page = locator.get("page")
    sheet = locator.get("sheet")
    line_start = locator.get("line_start")
    line_end = locator.get("line_end")

    parts: list[str] = []
    if page:
        parts.append(f"Página {page}")
    if sheet:
        parts.append(f"Aba {sheet}")
    if line_start and line_end and line_start == line_end:
        parts.append(f"Linha {line_start}")
    elif line_start and line_end:
        parts.append(f"Linhas {line_start}-{line_end}")
    elif line_start:
        parts.append(f"Linha {line_start}")
    return " | ".join(parts) or None


def block_display_title(block: dict, fallback_index: int) -> str:
    extra = block.get("extra", {})
    if extra.get("display_title"):
        return str(extra["display_title"])
    title = block.get("title")
    if title:
        return str(title)
    text = " ".join(str(block.get("text") or "").split())
    if not text:
        return f"Bloco {fallback_index}"
    if len(text) <= 96:
        return text
    return f"{text[:93].rstrip()}..."


def block_text_preview(text: str, max_length: int = 220) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3].rstrip()}..."


def block_source_reference(block: dict, fallback_index: int) -> str:
    locator = block.get("locator", {}) or {}
    display_title = block_display_title(block, fallback_index)
    locator_path = format_locator_path(locator)
    position_text = format_position(locator)

    parts = [display_title]
    if locator_path and locator_path != block.get("title"):
        parts.append(locator_path)
    if position_text:
        parts.append(position_text)
    parts.append(block.get("id") or f"block_{fallback_index:04d}")
    return " | ".join(parts)


def _flatten_index_count(entries: list[dict]) -> int:
    count = 0
    for entry in entries:
        count += 1
        count += _flatten_index_count(entry.get("children") or [])
    return count


def _count_descendants(entry: dict) -> int:
    children = entry.get("children") or []
    count = len(children)
    for child in children:
        count += _count_descendants(child)
    return count


def _collect_structure_counts(blocks: list[dict]) -> dict[str, int]:
    counts = Counter(block.get("kind") for block in blocks if block.get("kind") in STRUCTURE_KIND_ORDER)
    return {kind: counts[kind] for kind in STRUCTURE_KIND_ORDER if counts[kind]}


def _infer_domain(document_archetype: DocumentArchetype, parser_metadata: dict, structure_counts: dict[str, int], blocks: list[dict]) -> str:
    if document_archetype in {"legislation_normative", "legislation_amending_act"}:
        return "legal_normative"
    if document_archetype == "judicial_case":
        return "judicial_document"
    if document_archetype == "spreadsheet_structured":
        return "tabular_document"
    if document_archetype in {"xml_structured", "financial_statement_ofx"}:
        return "structured_data_document"

    if structure_counts.get("article") or structure_counts.get("part") or parser_metadata.get("mode") == "structured_legal":
        return "legal_normative"

    kinds = {block.get("kind") for block in blocks}
    if {"table_header", "table_row", "sheet_row"} & kinds:
        return "tabular_document"
    if {"xml_node"} & kinds:
        return "structured_data_document"
    return "general_text_document"


def _infer_primary_structure(parser_metadata: dict, structure_counts: dict[str, int]) -> str:
    mode = parser_metadata.get("mode")
    if mode:
        return str(mode)
    if structure_counts:
        return "structured_legal"
    return "flat_blocks"


def build_content_payload(
    metadata: dict,
    content: dict,
    index_entries: list[dict],
    summary: str,
    *,
    document_archetype: DocumentArchetype,
) -> dict:
    parser_metadata = dict(content.get("parser_metadata", {}))
    source_blocks = content.get("blocks", [])

    blocks: list[dict] = []
    for index, block in enumerate(source_blocks, start=1):
        locator = dict(block.get("locator", {}) or {})
        enriched_block = dict(block)
        enriched_block["display_title"] = block_display_title(block, index)
        enriched_block["hierarchy_path"] = extract_hierarchy_path(locator)
        enriched_block["locator_path"] = format_locator_path(locator)
        enriched_block["position_text"] = format_position(locator)
        enriched_block["source_reference"] = block_source_reference(block, index)
        enriched_block["text_preview"] = block_text_preview(str(block.get("text") or ""))
        blocks.append(enriched_block)

    structure_counts = _collect_structure_counts(blocks)
    document_profile = {
        "domain": _infer_domain(document_archetype, parser_metadata, structure_counts, blocks),
        "document_archetype": document_archetype,
        "primary_structure": _infer_primary_structure(parser_metadata, structure_counts),
        "block_count": len(blocks),
        "index_entry_count": _flatten_index_count(index_entries),
        "structure_counts": structure_counts,
        "top_level_index_titles": [entry.get("title") for entry in index_entries[:20]],
        "consultation_goal": "upload único para consulta, parecer, análise, diagnóstico e resposta fundamentada por IA",
    }

    ai_ready = {
        "single_file_ready": True,
        "preferred_upload_unit": False,
        "preferred_artifact_for_upload": "ai_context.json",
        "preferred_markdown_artifact_for_upload": "ai_context.md",
        "recommended_use": "payload enxuto para grounding estruturado, busca e citações diretas por bloco",
        "recommended_fields_for_grounding": [
            "summary",
            "index",
            "blocks[].display_title",
            "blocks[].source_reference",
            "blocks[].text",
        ],
        "recommended_workflow": [
            "Use o índice para localizar o dispositivo ou seção pertinente.",
            "Busque o bloco pelo display_title, source_reference ou block id.",
            "Fundamente a resposta com o texto integral do bloco e sua referência estrutural.",
            "Se a conclusão depender de múltiplos blocos, cite cada referência separadamente.",
        ],
        "answering_rules": [
            "Não invente conteúdo ausente no arquivo.",
            "Priorize o texto-fonte do bloco antes de inferir interpretação.",
            "Quando houver ambiguidade, explicite a limitação e cite os blocos relevantes.",
            "Use source_reference e block id para citar a origem da informação.",
        ],
        "citation_template": "{source_reference}",
    }

    return {
        "blocks": blocks,
        "document_archetype": document_archetype,
        "parser_metadata": parser_metadata,
        "metadata": metadata,
        "summary": summary,
        "index": index_entries,
        "document_profile": document_profile,
        "ai_ready": ai_ready,
    }


def build_index_payload(metadata: dict, consultation_payload: dict) -> list[dict]:
    blocks = consultation_payload.get("blocks", [])
    block_by_index: dict[int, dict] = {
        index: block for index, block in enumerate(blocks, start=1)
    }
    document_context = {
        "file_name": metadata.get("file_name"),
        "file_type": metadata.get("file_type"),
        "domain": consultation_payload.get("document_profile", {}).get("domain"),
        "document_archetype": consultation_payload.get("document_profile", {}).get("document_archetype"),
        "primary_structure": consultation_payload.get("document_profile", {}).get("primary_structure"),
        "citation_template": consultation_payload.get("ai_ready", {}).get("citation_template"),
    }

    def enrich(entries: list[dict]) -> list[dict]:
        enriched_entries: list[dict] = []
        for entry in entries:
            entry_copy = dict(entry)
            try:
                block_position = int(str(entry_copy.get("id", "")).split("_")[-1])
            except ValueError:
                block_position = None

            block = block_by_index.get(block_position) if block_position is not None else None
            locator = dict(entry_copy.get("locator", {}) or {})
            entry_copy["display_title"] = entry_copy.get("title")
            entry_copy["hierarchy_path"] = extract_hierarchy_path(locator)
            entry_copy["locator_path"] = format_locator_path(locator)
            entry_copy["position_text"] = format_position(locator)
            entry_copy["source_reference"] = (
                block.get("source_reference") if block else block_source_reference({"title": entry_copy.get("title"), "locator": locator}, block_position or 0)
            )
            entry_copy["text_preview"] = block.get("text_preview") if block else None
            entry_copy["summary"] = (block.get("extra", {}) or {}).get("summary") if block else None
            entry_copy["document_context"] = document_context
            entry_copy["search_text"] = " | ".join(
                str(part)
                for part in (
                    entry_copy.get("title"),
                    entry_copy.get("locator_path"),
                    entry_copy.get("text_preview"),
                )
                if part
            )
            entry_copy["children"] = enrich(entry_copy.get("children") or [])
            entry_copy["descendant_count"] = _count_descendants(entry_copy)
            enriched_entries.append(entry_copy)
        return enriched_entries

    return enrich(consultation_payload.get("index", []))


def build_metadata_payload(metadata: dict, consultation_payload: dict) -> dict:
    payload = dict(metadata)
    payload["artifact_role"] = "document_manifest"
    payload["document_archetype"] = consultation_payload.get("document_profile", {}).get("document_archetype")
    payload["document_profile"] = consultation_payload.get("document_profile", {})
    payload["consultation_hints"] = {
        "summary": consultation_payload.get("summary"),
        "top_level_index_titles": consultation_payload.get("document_profile", {}).get("top_level_index_titles", []),
        "preferred_artifact_for_grounding": "ai_context.json",
        "compact_grounding_artifact": "content.json",
        "preferred_markdown_artifact_for_upload": "ai_context.md",
        "human_plus_ai_review_artifact": "summary.md",
        "alternative_artifact_for_human_plus_ai_review": "summary.md",
        "citation_template": consultation_payload.get("ai_ready", {}).get("citation_template"),
        "recommended_workflow": consultation_payload.get("ai_ready", {}).get("recommended_workflow", []),
        "answering_rules": consultation_payload.get("ai_ready", {}).get("answering_rules", []),
    }
    payload["available_artifacts"] = {
        "ai_context": "ai_context.json",
        "ai_context_markdown": "ai_context.md",
        "metadata": "metadata.json",
        "index": "index.json",
        "content": "content.json",
        "summary": "summary.md",
        "report": "report.html",
    }
    payload["ai_ready"] = {
        "single_file_ready": False,
        "recommended_use": "manifesto de triagem e roteamento; para upload único prefira ai_context.json",
        "domain": consultation_payload.get("document_profile", {}).get("domain"),
        "primary_structure": consultation_payload.get("document_profile", {}).get("primary_structure"),
        "preferred_artifact_for_upload": "ai_context.json",
        "preferred_markdown_artifact_for_upload": "ai_context.md",
    }
    return payload


def build_ai_context_payload(
    metadata_payload: dict,
    consultation_payload: dict,
    index_payload: list[dict],
) -> dict:
    document_profile = consultation_payload.get("document_profile", {})
    ai_ready = dict(consultation_payload.get("ai_ready", {}))
    ai_ready["single_file_ready"] = True
    ai_ready["preferred_upload_unit"] = True
    ai_ready["preferred_artifact_for_upload"] = "ai_context.json"
    ai_ready["preferred_markdown_artifact_for_upload"] = "ai_context.md"
    ai_ready["recommended_use"] = "artefato único recomendado para upload em IA com grounding, navegação estrutural e citações"

    return {
        "artifact_role": "ai_context_bundle",
        "schema_version": "1.0",
        "document_archetype": document_profile.get("document_archetype"),
        "document_profile": document_profile,
        "metadata": metadata_payload,
        "consultation_hints": metadata_payload.get("consultation_hints", {}),
        "parser_metadata": consultation_payload.get("parser_metadata", {}),
        "summary": consultation_payload.get("summary", ""),
        "index": index_payload,
        "blocks": consultation_payload.get("blocks", []),
        "ai_ready": ai_ready,
    }
