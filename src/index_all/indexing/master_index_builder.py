from __future__ import annotations

from copy import deepcopy
from typing import Sequence


def _prefix_master_entries(
    entries: Sequence[dict],
    *,
    prefix: str,
    parent_id: str,
    level_offset: int,
    parent_path: list[str] | None = None,
    file_name: str | None = None,
    file_type: str | None = None,
    document_archetype: str | None = None,
    output_dir: str | None = None,
) -> list[dict]:
    prefixed_entries: list[dict] = []
    current_path = list(parent_path or [])

    for index, entry in enumerate(entries, start=1):
        entry_copy = deepcopy(entry)
        base_id = str(entry_copy.get("id") or f"entry_{index:04d}")
        entry_id = f"{prefix}_{base_id}"
        title = str(entry_copy.get("title") or f"Entrada {index}")

        entry_copy["id"] = entry_id
        entry_copy["parent_id"] = parent_id
        entry_copy["heading_path"] = current_path + [title]
        entry_copy["heading_path_text"] = " > ".join(entry_copy["heading_path"])
        entry_copy["file_name"] = file_name
        entry_copy["file_type"] = file_type
        entry_copy["document_archetype"] = document_archetype
        entry_copy["output_dir"] = output_dir

        level = entry_copy.get("level")
        if isinstance(level, int):
            entry_copy["level"] = level + level_offset
        else:
            entry_copy["level"] = level_offset + 1

        entry_copy["children"] = _prefix_master_entries(
            entry_copy.get("children") or [],
            prefix=prefix,
            parent_id=entry_id,
            level_offset=level_offset,
            parent_path=entry_copy["heading_path"],
            file_name=file_name,
            file_type=file_type,
            document_archetype=document_archetype,
            output_dir=output_dir,
        )
        prefixed_entries.append(entry_copy)

    return prefixed_entries


def build_master_index(processed_documents: Sequence[dict]) -> list[dict]:
    master_index: list[dict] = []

    for index, processed_document in enumerate(processed_documents, start=1):
        metadata = dict(processed_document.get("metadata", {}) or {})
        content = dict(processed_document.get("content", {}) or {})
        index_entries = list(processed_document.get("index", []) or [])
        document_profile = dict(content.get("document_profile", {}) or metadata.get("document_profile", {}) or {})

        document_node_id = f"master_{index:04d}"
        document_node = {
            "file_name": metadata.get("file_name"),
            "file_type": metadata.get("file_type"),
            "document_archetype": content.get("document_archetype") or metadata.get("document_archetype"),
            "output_dir": str(processed_document.get("output_dir") or ""),
            "id": document_node_id,
            "title": metadata.get("file_name") or f"Documento {index}",
            "kind": "document",
            "level": 1,
            "parent_id": None,
            "heading_path": [metadata.get("file_name") or f"Documento {index}"],
            "heading_path_text": metadata.get("file_name") or f"Documento {index}",
            "block_count": document_profile.get("block_count", len(content.get("blocks", []) or [])),
            "index_entry_count": document_profile.get("index_entry_count", len(index_entries)),
            "children": _prefix_master_entries(
                index_entries,
                prefix=document_node_id,
                parent_id=document_node_id,
                level_offset=1,
                parent_path=[metadata.get("file_name") or f"Documento {index}"],
                file_name=metadata.get("file_name"),
                file_type=metadata.get("file_type"),
                document_archetype=content.get("document_archetype") or metadata.get("document_archetype"),
                output_dir=str(processed_document.get("output_dir") or ""),
            ),
        }
        master_index.append(document_node)

    return master_index
