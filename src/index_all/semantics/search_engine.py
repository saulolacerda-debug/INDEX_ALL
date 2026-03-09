from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position


def _normalize_text(value: Any) -> str:
    compact = " ".join(str(value or "").split()).strip().lower()
    if not compact:
        return ""
    normalized = unicodedata.normalize("NFKD", compact)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _query_tokens(query: str) -> list[str]:
    return [token for token in re.split(r"\W+", _normalize_text(query)) if token]


def _snippet(text: str, query: str, max_length: int = 220) -> str:
    compact = " ".join(str(text or "").split()).strip()
    if not compact:
        return ""

    normalized_text = _normalize_text(compact)
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return compact[:max_length]

    position = normalized_text.find(normalized_query)
    if position == -1:
        tokens = _query_tokens(query)
        position = next((normalized_text.find(token) for token in tokens if token and normalized_text.find(token) != -1), -1)
        if position == -1:
            return compact[:max_length]

    start = max(position - 60, 0)
    end = min(start + max_length, len(compact))
    snippet = compact[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(compact):
        snippet = snippet + "..."
    return snippet


def score_text_record(
    query: str,
    *,
    title: str = "",
    heading_path: Sequence[str] | None = None,
    text: str = "",
    file_name: str = "",
) -> int:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return 0

    tokens = _query_tokens(query)
    title_text = _normalize_text(title)
    heading_text = _normalize_text(" ".join(heading_path or []))
    body_text = _normalize_text(text)
    file_text = _normalize_text(file_name)
    full_text = " ".join(part for part in (title_text, heading_text, body_text, file_text) if part)

    score = 0
    if normalized_query in full_text:
        score += 8

    for token in tokens:
        if token in title_text:
            score += 4
        if token in heading_text:
            score += 3
        if token in body_text:
            score += 1
        if token in file_text:
            score += 2

    return score


def _matches_filters(record: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    if not filters:
        return True

    for key in ("file_type", "document_archetype", "file_name"):
        if key not in filters or filters[key] in (None, "", []):
            continue
        filter_value = filters[key]
        record_value = str(record.get(key) or "")
        if isinstance(filter_value, (list, tuple, set)):
            if record_value not in {str(item) for item in filter_value}:
                return False
            continue
        if record_value != str(filter_value):
            return False

    return True


def _flatten_entries(entries: Sequence[dict], *, source_kind: str, file_name: str, file_type: str, document_archetype: str) -> list[dict]:
    flattened: list[dict] = []

    def walk(nodes: Sequence[dict], path: list[str] | None = None) -> None:
        current_path = list(path or [])
        for node in nodes:
            heading_path = current_path + [str(node.get("title") or "Sem título")]
            node_file_name = node.get("file_name") or file_name
            node_file_type = node.get("file_type") or file_type
            node_document_archetype = node.get("document_archetype") or document_archetype
            flattened.append(
                {
                    "record_id": node.get("id"),
                    "source_kind": source_kind,
                    "file_name": node_file_name,
                    "file_type": node_file_type,
                    "document_archetype": node_document_archetype,
                    "title": node.get("title") or "",
                    "heading": node.get("title") or "",
                    "heading_path": heading_path,
                    "text": " | ".join(
                        str(part)
                        for part in (node.get("title"), node.get("locator_path"), node.get("text_preview"))
                        if part
                    ),
                    "locator": dict(node.get("locator", {}) or {}),
                    "position_text": node.get("position_text"),
                    "output_dir": node.get("output_dir"),
                }
            )
            walk(node.get("children") or [], path=heading_path)

    walk(entries)
    return flattened


def build_file_search_records(processed_document: Mapping[str, Any]) -> list[dict]:
    metadata = dict(processed_document.get("metadata", {}) or {})
    content = dict(processed_document.get("content", {}) or {})
    index_entries = list(processed_document.get("index", []) or [])
    file_name = str(metadata.get("file_name") or "")
    file_type = str(metadata.get("file_type") or "")
    document_archetype = str(content.get("document_archetype") or metadata.get("document_archetype") or "generic_document")
    output_dir = str(processed_document.get("output_dir") or "")

    records: list[dict] = [
        {
            "record_id": f"metadata::{file_name}",
            "source_kind": "metadata",
            "file_name": file_name,
            "file_type": file_type,
            "document_archetype": document_archetype,
            "title": file_name,
            "heading": file_name,
            "heading_path": [file_name],
            "text": " | ".join(
                str(part)
                for part in (
                    metadata.get("file_name"),
                    metadata.get("source_path"),
                    content.get("summary"),
                    " | ".join(content.get("document_profile", {}).get("top_level_index_titles", []) or []),
                )
                if part
            ),
            "locator": {},
            "position_text": None,
            "output_dir": output_dir,
        }
    ]

    for index, block in enumerate(content.get("blocks", []) or [], start=1):
        heading_path = list(block.get("hierarchy_path") or [])
        heading = block.get("display_title") or block.get("title") or f"Bloco {index}"
        if not heading_path:
            heading_path = [str(heading)]
        records.append(
            {
                "record_id": f"block::{block.get('id') or index}",
                "source_kind": "block",
                "file_name": file_name,
                "file_type": file_type,
                "document_archetype": document_archetype,
                "title": str(heading),
                "heading": str(heading),
                "heading_path": heading_path,
                "text": str(block.get("text") or ""),
                "locator": dict(block.get("locator", {}) or {}),
                "position_text": block.get("position_text") or format_position(dict(block.get("locator", {}) or {})),
                "output_dir": output_dir,
            }
        )

    records.extend(
        _flatten_entries(
            index_entries,
            source_kind="index",
            file_name=file_name,
            file_type=file_type,
            document_archetype=document_archetype,
        )
    )
    for record in records:
        record.setdefault("output_dir", output_dir)
    return records


def build_search_index(processed_documents: Sequence[Mapping[str, Any]], catalog: Sequence[Mapping[str, Any]], master_index: Sequence[Mapping[str, Any]]) -> dict:
    records: list[dict] = []
    for processed_document in processed_documents:
        records.extend(build_file_search_records(processed_document))

    for entry in catalog:
        records.append(
            {
                "record_id": entry.get("id"),
                "source_kind": "catalog",
                "file_name": entry.get("file_name"),
                "file_type": entry.get("file_type"),
                "document_archetype": entry.get("document_archetype"),
                "title": entry.get("file_name") or "",
                "heading": entry.get("file_name") or "",
                "heading_path": [str(entry.get("file_name") or "")],
                "text": " | ".join(
                    str(part)
                    for part in (
                        entry.get("file_name"),
                        entry.get("document_archetype"),
                        " | ".join(entry.get("top_index_titles", []) or []),
                    )
                    if part
                ),
                "locator": {},
                "position_text": None,
                "output_dir": entry.get("output_dir"),
            }
        )

    records.extend(
        _flatten_entries(
            master_index,
            source_kind="master_index",
            file_name="",
            file_type="",
            document_archetype="collection",
        )
    )

    return {
        "metadata": {
            "artifact_role": "collection_search_index",
            "record_count": len(records),
            "supported_filters": ["file_type", "document_archetype", "file_name"],
        },
        "records": records,
    }


def _read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_processed_dir(file_path: str | Path) -> Path:
    candidate = Path(file_path)
    if candidate.is_file():
        return candidate.parent
    return candidate


def load_processed_document(file_path: str | Path) -> dict:
    processed_dir = _resolve_processed_dir(file_path)
    return {
        "metadata": _read_json(processed_dir / "metadata.json"),
        "content": _read_json(processed_dir / "content.json"),
        "index": _read_json(processed_dir / "index.json"),
        "output_dir": str(processed_dir.resolve()),
    }


def _default_collection_dir() -> Path:
    candidate = Path.cwd()
    if (candidate / "search_index.json").exists() or (candidate / "catalog.json").exists():
        return candidate
    raise FileNotFoundError("Collection directory not provided and no collection artifacts found in the current directory.")


def _load_search_index(collection_dir: str | Path | None) -> dict:
    resolved_dir = Path(collection_dir) if collection_dir is not None else _default_collection_dir()
    search_index_path = resolved_dir / "search_index.json"
    if search_index_path.exists():
        return _read_json(search_index_path)

    catalog = list(_read_json(resolved_dir / "catalog.json"))
    master_index = list(_read_json(resolved_dir / "master_index.json"))
    processed_documents = [load_processed_document(entry["output_dir"]) for entry in catalog]
    return build_search_index(processed_documents, catalog, master_index)


def _search_records(query: str, records: Iterable[Mapping[str, Any]], *, filters: Mapping[str, Any] | None = None, limit: int = 10) -> list[dict]:
    results: list[dict] = []

    for record in records:
        if not _matches_filters(record, filters):
            continue

        score = score_text_record(
            query,
            title=str(record.get("title") or ""),
            heading_path=list(record.get("heading_path") or []),
            text=str(record.get("text") or ""),
            file_name=str(record.get("file_name") or ""),
        )
        if score <= 0:
            continue

        locator = dict(record.get("locator", {}) or {})
        results.append(
            {
                "record_id": record.get("record_id"),
                "source_kind": record.get("source_kind"),
                "file_name": record.get("file_name"),
                "file_type": record.get("file_type"),
                "document_archetype": record.get("document_archetype"),
                "heading": record.get("heading") or record.get("title"),
                "heading_path": list(record.get("heading_path") or []),
                "snippet": _snippet(str(record.get("text") or record.get("title") or ""), query),
                "locator": locator,
                "locator_path": format_locator_path(locator),
                "position_text": record.get("position_text") or format_position(locator),
                "output_dir": record.get("output_dir"),
                "score": score,
            }
        )

    return sorted(results, key=lambda item: (-int(item["score"]), str(item.get("file_name") or ""), str(item.get("heading") or "")))[:limit]


def search_file(query: str, file_path: str | Path, limit: int = 10, filters: Mapping[str, Any] | None = None) -> dict:
    processed_document = load_processed_document(file_path)
    records = build_file_search_records(processed_document)
    results = _search_records(query, records, filters=filters, limit=limit)
    return {
        "query": query,
        "filters": dict(filters or {}),
        "total_hits": len(results),
        "results": results,
    }


def search_collection(
    query: str,
    filters: Mapping[str, Any] | None = None,
    limit: int = 10,
    *,
    collection_dir: str | Path | None = None,
) -> dict:
    search_index = _load_search_index(collection_dir)
    records = list(search_index.get("records", []) or [])
    results = _search_records(query, records, filters=filters, limit=limit)
    return {
        "query": query,
        "filters": dict(filters or {}),
        "total_hits": len(results),
        "results": results,
    }
