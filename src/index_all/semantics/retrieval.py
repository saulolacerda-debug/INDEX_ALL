from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position
from index_all.semantics.chunker import build_collection_chunks
from index_all.semantics.search_engine import load_processed_document, score_text_record


def _read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _matches_filters(chunk: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    if not filters:
        return True

    for key in ("document_archetype", "file_name", "file_type"):
        if key not in filters or filters[key] in (None, "", []):
            continue
        filter_value = filters[key]
        chunk_value = str(chunk.get(key) or "")
        if isinstance(filter_value, (list, tuple, set)):
            if chunk_value not in {str(item) for item in filter_value}:
                return False
            continue
        if chunk_value != str(filter_value):
            return False

    return True


def search_chunks(query: str, chunks: Sequence[dict], *, filters: Mapping[str, Any] | None = None, limit: int = 6) -> list[dict]:
    ranked: list[dict] = []
    for chunk in chunks:
        if not _matches_filters(chunk, filters):
            continue
        score = score_text_record(
            query,
            title=str(chunk.get("heading") or ""),
            heading_path=list(chunk.get("heading_path") or []),
            text=str(chunk.get("text") or ""),
            file_name=str(chunk.get("file_name") or ""),
        )
        if score <= 0:
            continue
        ranked.append({**chunk, "score": score})

    return sorted(
        ranked,
        key=lambda item: (-int(item["score"]), str(item.get("file_name") or ""), str(item.get("heading") or "")),
    )[:limit]


def _load_chunks(collection_dir: Path) -> list[dict]:
    chunks_path = collection_dir / "chunks.json"
    if chunks_path.exists():
        payload = _read_json(chunks_path)
        return list(payload.get("records", []) or payload.get("chunks", []) or [])

    catalog = list(_read_json(collection_dir / "catalog.json"))
    processed_documents = [load_processed_document(entry["output_dir"]) for entry in catalog]
    return build_collection_chunks(processed_documents)


def retrieve_context(query: str, collection_dir: str | Path, filters: Mapping[str, Any] | None = None, limit: int = 6) -> dict:
    resolved_dir = Path(collection_dir)
    ranked_chunks = search_chunks(query, _load_chunks(resolved_dir), filters=filters, limit=limit)

    context_lines: list[str] = []
    for index, chunk in enumerate(ranked_chunks, start=1):
        locator = dict(chunk.get("locator", {}) or {})
        locator_text = chunk.get("locator_path") or format_locator_path(locator)
        position_text = chunk.get("position_text") or format_position(locator)
        heading_path_text = chunk.get("heading_path_text") or " > ".join(chunk.get("heading_path") or [])
        header_parts = [
            f"[{index}] {chunk.get('file_name')} ({chunk.get('document_archetype')})",
            heading_path_text,
        ]
        if locator_text:
            header_parts.append(locator_text)
        if position_text:
            header_parts.append(position_text)
        context_lines.append(" | ".join(part for part in header_parts if part))
        context_lines.append(str(chunk.get("text") or ""))
        context_lines.append("")

    return {
        "query": query,
        "filters": dict(filters or {}),
        "chunks": ranked_chunks,
        "context_text": "\n".join(context_lines).strip(),
    }


def build_retrieval_preview(chunks: Sequence[dict]) -> dict:
    sample_chunks = [
        {
            "chunk_id": chunk.get("chunk_id"),
            "file_name": chunk.get("file_name"),
            "document_archetype": chunk.get("document_archetype"),
            "heading_path_text": chunk.get("heading_path_text"),
            "locator_path": chunk.get("locator_path"),
        }
        for chunk in list(chunks)[:10]
    ]
    return {
        "artifact_role": "retrieval_preview",
        "mode": "textual_retrieval_ready",
        "chunk_count": len(chunks),
        "sample_chunks": sample_chunks,
        "supported_filters": ["document_archetype", "file_name", "file_type"],
    }
