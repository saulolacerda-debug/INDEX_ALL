from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position
from index_all.semantics.ranking_profiles import DEFAULT_RANKING_PROFILE, normalize_ranking_profile, uses_legal_reference_scoring

SOURCE_KIND_PRIORITY = {
    "chunk": 6,
    "index": 5,
    "block": 4,
    "master_index": 3,
    "catalog": 2,
    "metadata": 1,
}
SOURCE_KIND_SCORE_BOOST = {
    "chunk": 6,
    "index": 5,
    "block": 3,
    "master_index": 2,
    "catalog": 1,
    "metadata": 0,
}
SPECIALIZED_ARCHETYPES = {
    "legislation_normative",
    "legislation_amending_act",
    "manual_procedural",
    "judicial_case",
    "spreadsheet_structured",
    "xml_structured",
    "financial_statement_ofx",
}
LEGAL_REFERENCE_ART_PATTERN = re.compile(r"\bart(?:igo)?\.?\s*(\d{1,4})(?:\s*[-]?\s*([a-z]))?\b", re.IGNORECASE)
LEGAL_REFERENCE_BARE_PATTERN = re.compile(r"\b(\d{1,4})\s*-\s*([a-z])\b", re.IGNORECASE)


def normalize_text(value: Any) -> str:
    compact = " ".join(str(value or "").split()).strip().lower()
    if not compact:
        return ""
    normalized = unicodedata.normalize("NFKD", compact)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def query_tokens(query: str) -> list[str]:
    return [token for token in re.split(r"\W+", normalize_text(query)) if token and (len(token) > 1 or token.isdigit())]


def _normalize_legal_reference(number: str, suffix: str | None = None) -> str:
    normalized_number = re.sub(r"\D+", "", str(number or ""))
    normalized_suffix = normalize_text(suffix or "").strip("- ")
    if not normalized_number:
        return ""
    return f"{normalized_number}-{normalized_suffix}" if normalized_suffix else normalized_number


def extract_legal_references(value: str, *, allow_bare: bool = False) -> list[str]:
    references: list[str] = []
    raw_value = str(value or "")

    for match in LEGAL_REFERENCE_ART_PATTERN.finditer(raw_value):
        normalized = _normalize_legal_reference(match.group(1), match.group(2))
        if normalized:
            references.append(normalized)

    if allow_bare:
        for match in LEGAL_REFERENCE_BARE_PATTERN.finditer(raw_value):
            normalized = _normalize_legal_reference(match.group(1), match.group(2))
            if normalized:
                references.append(normalized)

    return list(dict.fromkeys(references))


def extract_primary_legal_reference(value: str) -> str | None:
    match = re.match(r'^\s*["“\(]*art(?:igo)?\.?\s*(\d{1,4})(?:\s*[-]?\s*([a-z]))?\b', str(value or ""), re.IGNORECASE)
    if not match:
        return None
    normalized = _normalize_legal_reference(match.group(1), match.group(2))
    return normalized or None


def legal_reference_details(
    query: str,
    *,
    title: str = "",
    heading_path: Sequence[str] | None = None,
    text: str = "",
) -> dict[str, Any]:
    query_references = extract_legal_references(query, allow_bare=True)
    if not query_references:
        return {
            "query_references": [],
            "title_exact": 0,
            "heading_exact": 0,
            "body_exact": 0,
            "title_partial_only": 0,
            "heading_partial_only": 0,
            "body_partial_only": 0,
        }

    title_refs = set(extract_legal_references(title, allow_bare=True))
    heading_refs = set(extract_legal_references(" ".join(heading_path or []), allow_bare=True))
    body_refs = set(extract_legal_references(text, allow_bare=True))
    details = {
        "query_references": query_references,
        "title_exact": 0,
        "heading_exact": 0,
        "body_exact": 0,
        "title_partial_only": 0,
        "heading_partial_only": 0,
        "body_partial_only": 0,
    }

    for reference in query_references:
        base_reference = reference.split("-", 1)[0]
        if reference in title_refs:
            details["title_exact"] += 1
        elif "-" in reference and base_reference in title_refs:
            details["title_partial_only"] += 1

        if reference in heading_refs:
            details["heading_exact"] += 1
        elif "-" in reference and base_reference in heading_refs:
            details["heading_partial_only"] += 1

        if reference in body_refs:
            details["body_exact"] += 1
        elif "-" in reference and base_reference in body_refs:
            details["body_partial_only"] += 1

    return details


def _snippet(text: str, query: str, max_length: int = 220) -> str:
    compact = " ".join(str(text or "").split()).strip()
    if not compact:
        return ""

    normalized_text = normalize_text(compact)
    normalized_query = normalize_text(query)
    if not normalized_query:
        return compact[:max_length]

    position = normalized_text.find(normalized_query)
    if position == -1:
        tokens = query_tokens(query)
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


def _heading_path_text(record: Mapping[str, Any]) -> str:
    heading_path = [str(part).strip() for part in (record.get("heading_path") or []) if str(part).strip()]
    if heading_path:
        return " > ".join(heading_path)
    for fallback in (record.get("heading"), record.get("title")):
        if str(fallback or "").strip():
            return str(fallback).strip()
    return ""


def _count_token_occurrences(text: str, token: str) -> int:
    if not text or not token:
        return 0
    matches = re.findall(rf"(?<!\w){re.escape(token)}(?!\w)", text)
    if matches:
        return len(matches)
    return text.count(token)


def score_text_match(
    query: str,
    *,
    title: str = "",
    heading_path: Sequence[str] | None = None,
    text: str = "",
    file_name: str = "",
    document_archetype: str = "",
    source_kind: str = "",
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> dict[str, Any]:
    normalized_profile = normalize_ranking_profile(ranking_profile)
    normalized_query = normalize_text(query)
    if not normalized_query:
        return {"score": 0, "score_breakdown": {}}

    tokens = list(dict.fromkeys(query_tokens(query)))
    title_text = normalize_text(title)
    heading_text = normalize_text(" ".join(heading_path or []))
    body_text = normalize_text(text)
    file_text = normalize_text(file_name)
    archetype_text = normalize_text(document_archetype)
    breakdown: dict[str, int] = {}

    def add(label: str, value: int) -> None:
        if value:
            breakdown[label] = breakdown.get(label, 0) + int(value)

    if normalized_query in title_text:
        add("title_phrase", 12)
    if normalized_query in heading_text:
        add("heading_phrase", 10 if normalized_query not in title_text else 4)
    if normalized_query in body_text:
        add("body_phrase", 4)
    if normalized_query in file_text:
        add("file_name_phrase", 5)

    title_hits = sum(1 for token in tokens if token in title_text)
    heading_hits = sum(1 for token in tokens if token in heading_text)
    file_hits = sum(1 for token in tokens if token in file_text)
    archetype_hits = sum(1 for token in tokens if token in archetype_text)
    body_occurrences = sum(min(_count_token_occurrences(body_text, token), 3) for token in tokens)
    body_hits = sum(1 for token in tokens if token in body_text)

    add("title_tokens", title_hits * 6)
    add("heading_tokens", heading_hits * 5)
    add("body_tokens", min(body_occurrences, max(len(tokens), 1) * 3) * 2)
    add("file_name_tokens", file_hits * 3)
    add("archetype_tokens", archetype_hits * 2)

    if uses_legal_reference_scoring(normalized_profile):
        legal_details = legal_reference_details(
            query,
            title=title,
            heading_path=heading_path,
            text=text,
        )
        add("legal_ref_title_exact", legal_details["title_exact"] * 26)
        add("legal_ref_heading_exact", legal_details["heading_exact"] * 24)
        add("legal_ref_body_exact", legal_details["body_exact"] * 8)
        add("legal_ref_title_partial_penalty", legal_details["title_partial_only"] * -14)
        add("legal_ref_heading_partial_penalty", legal_details["heading_partial_only"] * -12)
        add("legal_ref_body_partial_penalty", legal_details["body_partial_only"] * -4)
        primary_title_reference = extract_primary_legal_reference(title)
        for query_reference in legal_details["query_references"]:
            base_reference = query_reference.split("-", 1)[0]
            if primary_title_reference == query_reference:
                add("legal_ref_primary_title_exact", 42)
            elif "-" in query_reference and primary_title_reference == base_reference:
                add("legal_ref_primary_title_partial_penalty", -20)

    source_boost = SOURCE_KIND_SCORE_BOOST.get(source_kind, 0)
    if source_boost and (title_hits or heading_hits or body_hits or file_hits or normalized_query in body_text):
        add("source_kind", source_boost)

    if normalized_profile == "legal" and document_archetype in SPECIALIZED_ARCHETYPES:
        add("archetype_specificity", 1)

    text_length = len(" ".join(str(text or "").split()))
    if 80 <= text_length <= 900:
        add("length_fit", 2)
    elif 0 < text_length < 40:
        add("length_penalty", -1)
    elif text_length > 2200:
        add("length_penalty", -4)
    elif text_length > 1400:
        add("length_penalty", -2)

    repetition_penalty = sum(max(_count_token_occurrences(body_text, token) - 6, 0) for token in tokens)
    if repetition_penalty:
        add("repetition_penalty", -min(repetition_penalty, 6))

    score = sum(breakdown.values())
    has_signal = any(value > 0 for value in breakdown.values())
    if not has_signal or score <= 0:
        return {"score": 0, "score_breakdown": {}}
    return {"score": score, "score_breakdown": breakdown}


def score_text_record(
    query: str,
    *,
    title: str = "",
    heading_path: Sequence[str] | None = None,
    text: str = "",
    file_name: str = "",
    document_archetype: str = "",
    source_kind: str = "",
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> int:
    return int(
        score_text_match(
            query,
            title=title,
            heading_path=heading_path,
            text=text,
            file_name=file_name,
            document_archetype=document_archetype,
            source_kind=source_kind,
            ranking_profile=ranking_profile,
        )["score"]
    )


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

    def walk(nodes: Sequence[dict], *, path: list[str] | None = None) -> None:
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
                    "heading_path_text": " > ".join(heading_path),
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


def _block_heading_paths(blocks: Sequence[Mapping[str, Any]]) -> dict[int, list[str]]:
    paths: dict[int, list[str]] = {}
    heading_stack: list[dict[str, Any]] = []

    for index, block in enumerate(blocks, start=1):
        extra = dict(block.get("extra", {}) or {})
        if block.get("kind") == "heading":
            level = extra.get("heading_level")
            level = level if isinstance(level, int) else 1
            heading_stack = [item for item in heading_stack if int(item.get("level") or 0) < level]
            group = str(extra.get("heading_group") or extra.get("manual_group") or "")
            title = str(block.get("display_title") or block.get("title") or "").strip()
            if title and group != "interface":
                heading_stack.append({"level": level, "title": title})
            paths[index] = [str(item.get("title") or "") for item in heading_stack if str(item.get("title") or "").strip()]
            continue

        hierarchy_path = [str(part).strip() for part in (block.get("hierarchy_path") or []) if str(part).strip()]
        if hierarchy_path:
            paths[index] = hierarchy_path
            continue
        if heading_stack:
            paths[index] = [str(item.get("title") or "") for item in heading_stack if str(item.get("title") or "").strip()]
            continue
        fallback = str(block.get("display_title") or block.get("title") or f"Bloco {index}").strip()
        paths[index] = [fallback] if fallback else []

    return paths


def build_file_search_records(processed_document: Mapping[str, Any]) -> list[dict]:
    metadata = dict(processed_document.get("metadata", {}) or {})
    content = dict(processed_document.get("content", {}) or {})
    index_entries = list(processed_document.get("index", []) or [])
    blocks = list(content.get("blocks", []) or [])
    file_name = str(metadata.get("file_name") or "")
    file_type = str(metadata.get("file_type") or "")
    document_archetype = str(content.get("document_archetype") or metadata.get("document_archetype") or "generic_document")
    output_dir = str(processed_document.get("output_dir") or "")
    block_paths = _block_heading_paths(blocks)

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
            "heading_path_text": file_name,
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

    for index, block in enumerate(blocks, start=1):
        heading_path = list(block_paths.get(index) or [])
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
                "heading_path_text": " > ".join(heading_path),
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
        record["heading_path_text"] = record.get("heading_path_text") or _heading_path_text(record)
        record.setdefault("output_dir", output_dir)
    return records


def _record_signature_text(record: Mapping[str, Any], *, max_length: int = 240) -> str:
    title_text = normalize_text(record.get("title") or record.get("heading") or "")
    compact = normalize_text(record.get("text") or "")
    compact = re.sub(r"\bpagina\s+\d+\b", " ", compact)
    compact = re.sub(r"\blinhas?\s+\d+(?:-\d+)?\b", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip(" |-")
    if title_text and compact.startswith(title_text):
        compact = compact[len(title_text) :].strip(" |-")
    return compact[:max_length]


def _record_signature(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_text(record.get("file_name") or ""),
        normalize_text(record.get("heading_path_text") or _heading_path_text(record)),
        _record_signature_text(record),
    )


def _records_are_near_duplicates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if normalize_text(left.get("file_name") or "") != normalize_text(right.get("file_name") or ""):
        return False
    if normalize_text(left.get("heading_path_text") or _heading_path_text(left)) != normalize_text(
        right.get("heading_path_text") or _heading_path_text(right)
    ):
        return False

    left_signature = _record_signature_text(left, max_length=320)
    right_signature = _record_signature_text(right, max_length=320)
    if not left_signature or not right_signature:
        return False
    if left_signature == right_signature:
        return True

    shorter, longer = sorted((left_signature, right_signature), key=len)
    if len(shorter) < 48:
        return False
    return longer.startswith(shorter) or shorter in longer


def _record_quality(record: Mapping[str, Any]) -> tuple[int, int, int, int]:
    locator = dict(record.get("locator", {}) or {})
    locator_bonus = 1 if any(locator.values()) else 0
    return (
        SOURCE_KIND_PRIORITY.get(str(record.get("source_kind") or ""), 0),
        locator_bonus,
        len(normalize_text(record.get("text") or "")),
        len(normalize_text(record.get("heading_path_text") or _heading_path_text(record))),
    )


def _merge_records(preferred: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict:
    winner, loser = (preferred, candidate)
    if _record_quality(candidate) > _record_quality(preferred):
        winner, loser = candidate, preferred

    merged = dict(winner)
    if len(normalize_text(loser.get("text") or "")) > len(normalize_text(merged.get("text") or "")) and (
        SOURCE_KIND_PRIORITY.get(str(loser.get("source_kind") or ""), 0)
        >= SOURCE_KIND_PRIORITY.get(str(merged.get("source_kind") or ""), 0) - 1
    ):
        merged["text"] = loser.get("text")

    for field in ("locator", "position_text", "output_dir", "heading_path", "heading_path_text", "file_type", "document_archetype"):
        if not merged.get(field) and loser.get(field):
            merged[field] = loser.get(field)
    return merged


def _deduplicate_records(records: Sequence[Mapping[str, Any]]) -> tuple[list[dict], dict[str, int]]:
    exact_map: dict[tuple[str, str, str], dict] = {}
    near_map: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    exact_removed = 0
    near_removed = 0

    for record in records:
        normalized = dict(record)
        normalized["heading_path_text"] = normalized.get("heading_path_text") or _heading_path_text(normalized)
        signature = _record_signature(normalized)
        if signature in exact_map:
            exact_map[signature] = _merge_records(exact_map[signature], normalized)
            exact_removed += 1
            continue

        approximate_signature = (signature[0], signature[1], signature[2][:140])
        existing_signature = near_map.get(approximate_signature)
        if existing_signature and existing_signature in exact_map and _records_are_near_duplicates(exact_map[existing_signature], normalized):
            exact_map[existing_signature] = _merge_records(exact_map[existing_signature], normalized)
            near_removed += 1
            continue

        exact_map[signature] = normalized
        near_map[approximate_signature] = signature

    deduplicated = list(exact_map.values())
    return deduplicated, {
        "raw_record_count": len(records),
        "deduplicated_record_count": len(deduplicated),
        "exact_duplicates_removed": exact_removed,
        "near_duplicates_removed": near_removed,
    }


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
                "heading_path_text": str(entry.get("file_name") or ""),
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
    deduplicated_records, dedup_stats = _deduplicate_records(records)

    return {
        "metadata": {
            "artifact_role": "collection_search_index",
            "record_count": dedup_stats["deduplicated_record_count"],
            **dedup_stats,
            "supported_filters": ["file_type", "document_archetype", "file_name"],
        },
        "records": deduplicated_records,
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


def _search_records(
    query: str,
    records: Iterable[Mapping[str, Any]],
    *,
    filters: Mapping[str, Any] | None = None,
    limit: int = 10,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> list[dict]:
    normalized_profile = normalize_ranking_profile(ranking_profile)
    results: list[dict] = []

    for record in records:
        if not _matches_filters(record, filters):
            continue

        text = str(record.get("text") or record.get("title") or "")
        match = score_text_match(
            query,
            title=str(record.get("title") or ""),
            heading_path=list(record.get("heading_path") or []),
            text=text,
            file_name=str(record.get("file_name") or ""),
            document_archetype=str(record.get("document_archetype") or ""),
            source_kind=str(record.get("source_kind") or ""),
            ranking_profile=normalized_profile,
        )
        score = int(match["score"])
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
                "heading_path_text": record.get("heading_path_text") or _heading_path_text(record),
                "snippet": _snippet(text, query),
                "locator": locator,
                "locator_path": format_locator_path(locator) or record.get("position_text") or format_position(locator),
                "position_text": record.get("position_text") or format_position(locator),
                "output_dir": record.get("output_dir"),
                "score": score,
                "score_breakdown": match["score_breakdown"],
                "_text_length": len(" ".join(text.split())),
            }
        )

    sorted_results = sorted(
        results,
        key=lambda item: (
            -int(item["score"]),
            int(item["_text_length"]),
            str(item.get("file_name") or ""),
            str(item.get("heading") or ""),
        ),
    )[:limit]
    for item in sorted_results:
        item.pop("_text_length", None)
    return sorted_results


def search_file(query: str, file_path: str | Path, limit: int = 10, filters: Mapping[str, Any] | None = None) -> dict:
    processed_document = load_processed_document(file_path)
    records, _ = _deduplicate_records(build_file_search_records(processed_document))
    results = _search_records(query, records, filters=filters, limit=limit)
    return {
        "query": query,
        "filters": dict(filters or {}),
        "total_hits": len(results),
        "ranking_profile": DEFAULT_RANKING_PROFILE,
        "results": results,
    }


def search_collection(
    query: str,
    filters: Mapping[str, Any] | None = None,
    limit: int = 10,
    *,
    collection_dir: str | Path | None = None,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> dict:
    search_index = _load_search_index(collection_dir)
    records = list(search_index.get("records", []) or [])
    normalized_profile = normalize_ranking_profile(ranking_profile)
    results = _search_records(query, records, filters=filters, limit=limit, ranking_profile=normalized_profile)
    return {
        "query": query,
        "filters": dict(filters or {}),
        "total_hits": len(results),
        "ranking_profile": normalized_profile,
        "results": results,
    }
