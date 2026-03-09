from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Sequence


NORMATIVE_ARCHETYPES = {"legislation_normative", "legislation_amending_act"}


def _top_titles(catalog: Sequence[dict], limit: int = 10) -> list[str]:
    title_counter: Counter[str] = Counter()
    for entry in catalog:
        for title in entry.get("top_index_titles", []) or []:
            title_counter[str(title)] += 1
    return [title for title, _ in title_counter.most_common(limit)]


def _flatten_master_entry_count(entries: Sequence[dict]) -> int:
    count = 0
    for entry in entries:
        count += 1
        count += _flatten_master_entry_count(entry.get("children") or [])
    return count


def build_collection_metadata(
    source_dir: Path,
    catalog: Sequence[dict],
    master_index: Sequence[dict],
) -> dict:
    file_type_counts = Counter(str(entry.get("file_type") or "unknown") for entry in catalog)
    archetype_counts = Counter(str(entry.get("document_archetype") or "generic_document") for entry in catalog)
    normative_files = [
        str(entry.get("file_name"))
        for entry in catalog
        if entry.get("document_archetype") in NORMATIVE_ARCHETYPES
    ]
    procedural_files = [
        str(entry.get("file_name"))
        for entry in catalog
        if entry.get("document_archetype") == "manual_procedural"
    ]

    return {
        "artifact_role": "collection_manifest",
        "collection_name": source_dir.name,
        "source_path": str(source_dir),
        "file_count": len(catalog),
        "total_block_count": sum(int(entry.get("block_count") or 0) for entry in catalog),
        "master_index_entry_count": _flatten_master_entry_count(master_index),
        "file_type_counts": dict(sorted(file_type_counts.items())),
        "document_archetype_counts": dict(sorted(archetype_counts.items())),
        "top_titles": _top_titles(catalog),
        "files_with_normative_structure": normative_files,
        "files_with_procedural_structure": procedural_files,
        "available_artifacts": {
            "catalog": "catalog.json",
            "master_index": "master_index.json",
            "collection_metadata": "collection_metadata.json",
            "collection_summary": "collection_summary.md",
            "collection_report": "collection_report.html",
        },
    }


def build_collection_summary(
    collection_metadata: dict,
    catalog: Sequence[dict],
    master_index: Sequence[dict],
) -> str:
    sections = [
        (
            f"Coleção `{collection_metadata.get('collection_name', 'colecao')}` com "
            f"{collection_metadata.get('file_count', 0)} arquivo(s) processado(s)."
        ),
        (
            f"Total de blocos extraídos: {collection_metadata.get('total_block_count', 0)}. "
            f"Entradas no índice mestre: {collection_metadata.get('master_index_entry_count', 0)}."
        ),
    ]

    file_type_counts = collection_metadata.get("file_type_counts", {})
    if file_type_counts:
        sections.append(
            "Arquivos por tipo: "
            + ", ".join(f"{file_type}: {count}" for file_type, count in file_type_counts.items())
            + "."
        )

    archetype_counts = collection_metadata.get("document_archetype_counts", {})
    if archetype_counts:
        sections.append(
            "Arquivos por arquétipo: "
            + ", ".join(f"{archetype}: {count}" for archetype, count in archetype_counts.items())
            + "."
        )

    top_titles = collection_metadata.get("top_titles", [])
    if top_titles:
        sections.append("Principais títulos encontrados: " + " | ".join(top_titles[:10]) + ".")

    normative_files = collection_metadata.get("files_with_normative_structure", [])
    if normative_files:
        sections.append("Arquivos com estrutura normativa: " + ", ".join(normative_files) + ".")

    procedural_files = collection_metadata.get("files_with_procedural_structure", [])
    if procedural_files:
        sections.append("Arquivos com estrutura procedural: " + ", ".join(procedural_files) + ".")

    if catalog:
        sections.append(
            "Arquivos do catálogo: " + " | ".join(str(entry.get("file_name")) for entry in catalog[:10] if entry.get("file_name")) + "."
        )

    if master_index:
        sections.append(
            "Primeiras raízes do índice mestre: "
            + " | ".join(str(entry.get("title")) for entry in master_index[:10] if entry.get("title"))
            + "."
        )

    return "\n\n".join(sections)
