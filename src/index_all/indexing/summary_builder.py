from __future__ import annotations

from collections import Counter


STRUCTURE_LABELS = {
    "preamble": "preâmbulo(s)",
    "part": "parte(s)",
    "book": "livro(s)",
    "title": "título(s)",
    "chapter": "capítulo(s)",
    "section": "seção(ões)",
    "subsection": "subseção(ões)",
    "article": "artigo(s)",
    "legal_paragraph": "parágrafo(s)",
    "inciso": "inciso(s)",
    "alinea": "alínea(s)",
    "item": "item(ns)",
}


def _has_meaningful_text(text: str) -> bool:
    return any(character.isalnum() for character in text)


def _collect_structure_counts(blocks: list[dict]) -> str | None:
    counts = Counter(block.get("kind") for block in blocks if block.get("kind") in STRUCTURE_LABELS)
    if not counts:
        return None

    ordered_parts = []
    for kind in (
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
    ):
        count = counts.get(kind)
        if count:
            ordered_parts.append(f"{count} {STRUCTURE_LABELS[kind]}")
    return ", ".join(ordered_parts)


def _render_outline(entries: list[dict], depth: int = 0, limit: int = 10) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        if len(lines) >= limit:
            break
        indent = "  " * depth
        lines.append(f"{indent}- [{entry.get('kind')}] {entry.get('title')}")
        children = entry.get("children") or []
        if children and len(lines) < limit:
            lines.extend(_render_outline(children, depth + 1, limit - len(lines)))
    return lines


def build_summary(metadata: dict, blocks: list[dict], index_entries: list[dict] | None = None) -> str:
    preview_texts = []
    ordered_blocks = [block for block in blocks if block.get("kind") != "table"]
    ordered_blocks.extend(block for block in blocks if block.get("kind") == "table")

    for block in ordered_blocks:
        text = (block.get("text") or "").strip()
        if text and _has_meaningful_text(text):
            preview_texts.append(text[:300])
        if len(preview_texts) == 5:
            break

    file_name = metadata.get("file_name", "unknown")
    file_type = metadata.get("file_type", "unknown")
    block_count = len(blocks)

    sections = [f"Arquivo `{file_name}` do tipo `{file_type}` com {block_count} bloco(s) extraído(s)."]

    structure_counts = _collect_structure_counts(blocks)
    if structure_counts:
        sections.append(f"Estrutura identificada: {structure_counts}.")

    if index_entries:
        outline_lines = _render_outline(index_entries)
        if outline_lines:
            sections.append("Primeiros itens do índice:\n\n" + "\n".join(outline_lines))

    if not preview_texts:
        sections.append("Não foi possível extrair conteúdo textual relevante.")
        return "\n\n".join(sections)

    preview = "\n\n".join(preview_texts)
    sections.append(f"Prévia de conteúdo:\n\n{preview}")
    return "\n\n".join(sections)
