from __future__ import annotations

from typing import Sequence


def _top_index_titles(index_entries: Sequence[dict], limit: int = 8) -> list[str]:
    return [str(entry.get("title")) for entry in index_entries[:limit] if entry.get("title")]


def build_catalog(processed_documents: Sequence[dict]) -> list[dict]:
    catalog: list[dict] = []

    for index, processed_document in enumerate(processed_documents, start=1):
        metadata = dict(processed_document.get("metadata", {}) or {})
        content = dict(processed_document.get("content", {}) or {})
        index_entries = list(processed_document.get("index", []) or [])
        document_profile = dict(content.get("document_profile", {}) or metadata.get("document_profile", {}) or {})

        block_count = document_profile.get("block_count")
        if not isinstance(block_count, int):
            block_count = len(content.get("blocks", []) or [])

        catalog.append(
            {
                "id": f"catalog_{index:04d}",
                "file_name": metadata.get("file_name"),
                "file_type": metadata.get("file_type"),
                "document_archetype": content.get("document_archetype") or metadata.get("document_archetype"),
                "output_dir": str(processed_document.get("output_dir") or ""),
                "top_index_titles": _top_index_titles(index_entries),
                "block_count": block_count,
                "index_entry_count": document_profile.get("index_entry_count", len(index_entries)),
            }
        )

    return catalog
