from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position
from index_all.outputs.json_writer import read_json
from index_all.semantics.chunker import build_collection_chunks
from index_all.semantics.embedding_store import LocalEmbeddingStore, build_local_embedding, cosine_similarity
from index_all.semantics.ranking_profiles import DEFAULT_RANKING_PROFILE, normalize_ranking_profile
from index_all.semantics.reranker import rerank_candidates
from index_all.semantics.search_engine import _snippet, load_processed_document, query_tokens, score_text_match

PREVIEW_STOPWORDS = {
    "arquivo",
    "documento",
    "titulo",
    "capitulo",
    "secao",
    "subsecao",
    "parte",
    "livro",
    "manual",
    "procedimento",
}


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


def _load_chunks(collection_dir: Path) -> list[dict]:
    store = LocalEmbeddingStore(collection_dir)
    chunks = store.load_chunks()
    if chunks:
        return store.hydrate_chunks(chunks)

    catalog = list(read_json(collection_dir / "catalog.json"))
    processed_documents = [load_processed_document(entry["output_dir"]) for entry in catalog]
    built_chunks = build_collection_chunks(processed_documents)
    return store.hydrate_chunks(built_chunks)


def _query_embedding(chunks: Sequence[Mapping[str, Any]], query: str) -> list[float] | None:
    first_embedding = next((chunk.get("embedding") for chunk in chunks if chunk.get("embedding")), None)
    if not first_embedding:
        return None
    return build_local_embedding(query, vector_size=len(first_embedding))


def _chunk_text_length(chunk: Mapping[str, Any]) -> int:
    metadata = dict(chunk.get("metadata", {}) or {})
    return int(metadata.get("text_length") or len(" ".join(str(chunk.get("text") or "").split())))


def search_chunks(
    query: str,
    chunks: Sequence[dict],
    *,
    filters: Mapping[str, Any] | None = None,
    limit: int = 6,
    min_vector_score: float = 0.12,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> list[dict]:
    normalized_profile = normalize_ranking_profile(ranking_profile)
    query_vector = _query_embedding(chunks, query)
    candidates: list[dict] = []

    for chunk in chunks:
        if not _matches_filters(chunk, filters):
            continue

        text = str(chunk.get("text") or "")
        text_match = score_text_match(
            query,
            title=str(chunk.get("heading") or ""),
            heading_path=list(chunk.get("heading_path") or []),
            text=text,
            file_name=str(chunk.get("file_name") or ""),
            document_archetype=str(chunk.get("document_archetype") or ""),
            source_kind=str(chunk.get("source_kind") or "chunk"),
            ranking_profile=normalized_profile,
        )
        text_score = float(text_match["score"])
        vector_score = cosine_similarity(query_vector, chunk.get("embedding")) if query_vector else 0.0
        has_embedding = chunk.get("embedding") is not None

        if text_score <= 0 and vector_score < min_vector_score:
            continue

        locator = dict(chunk.get("locator", {}) or {})
        candidates.append(
            {
                **dict(chunk),
                "heading_path_text": chunk.get("heading_path_text") or " > ".join(chunk.get("heading_path") or []),
                "locator_path": chunk.get("locator_path") or format_locator_path(locator) or format_position(locator),
                "position_text": chunk.get("position_text") or format_position(locator),
                "snippet": _snippet(text, query, max_length=260),
                "preview_text": _snippet(text, query, max_length=260),
                "text_score": round(text_score, 4),
                "text_score_breakdown": dict(text_match["score_breakdown"]),
                "vector_score": round(vector_score, 6),
                "has_embedding": has_embedding,
                "text_length": _chunk_text_length(chunk),
            }
        )

    return rerank_candidates(query, candidates, limit=limit, ranking_profile=normalized_profile)


def retrieve_context(
    query: str,
    collection_dir: str | Path,
    filters: Mapping[str, Any] | None = None,
    limit: int = 6,
    *,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> dict:
    resolved_dir = Path(collection_dir)
    normalized_profile = normalize_ranking_profile(ranking_profile)
    ranked_chunks = search_chunks(
        query,
        _load_chunks(resolved_dir),
        filters=filters,
        limit=limit,
        ranking_profile=normalized_profile,
    )

    context_lines: list[str] = []
    for index, chunk in enumerate(ranked_chunks, start=1):
        locator = dict(chunk.get("locator", {}) or {})
        locator_text = chunk.get("locator_path") or format_locator_path(locator) or format_position(locator)
        heading_path_text = chunk.get("heading_path_text") or " > ".join(chunk.get("heading_path") or [])
        header_parts = [
            f"[{index}] {chunk.get('file_name')} ({chunk.get('document_archetype')})",
            heading_path_text,
            f"score={chunk.get('score')}",
            f"text={chunk.get('text_score')}",
            f"vector={chunk.get('vector_score')}",
            chunk.get("retrieval_mode"),
        ]
        if locator_text:
            header_parts.append(locator_text)
        context_lines.append(" | ".join(str(part) for part in header_parts if part not in (None, "")))
        context_lines.append(str(chunk.get("text") or ""))
        context_lines.append("")

    return {
        "query": query,
        "filters": dict(filters or {}),
        "chunks": ranked_chunks,
        "context_text": "\n".join(context_lines).strip(),
        "mode": "hybrid" if any(chunk.get("retrieval_mode") == "hybrid" for chunk in ranked_chunks) else "textual",
        "ranking_profile": normalized_profile,
    }


def _compact_result(chunk: Mapping[str, Any]) -> dict:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "file_name": chunk.get("file_name"),
        "file_type": chunk.get("file_type"),
        "document_archetype": chunk.get("document_archetype"),
        "heading_path_text": chunk.get("heading_path_text") or " > ".join(chunk.get("heading_path") or []),
        "locator": dict(chunk.get("locator", {}) or {}),
        "locator_path": chunk.get("locator_path") or chunk.get("position_text"),
        "position_text": chunk.get("position_text"),
        "score": chunk.get("score", 0),
        "text_score": chunk.get("text_score", 0),
        "vector_score": chunk.get("vector_score", 0),
        "retrieval_mode": chunk.get("retrieval_mode", "textual"),
        "score_breakdown": dict(chunk.get("score_breakdown", {}) or {}),
        "text_score_breakdown": dict(chunk.get("text_score_breakdown", {}) or {}),
        "preview_text": chunk.get("preview_text") or _snippet(str(chunk.get("text") or ""), "", max_length=180),
        "text_preview": _snippet(str(chunk.get("text") or ""), "", max_length=180),
    }


def _default_preview_queries(chunks: Sequence[Mapping[str, Any]], *, limit: int = 3) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        candidates = [
            str(chunk.get("heading") or ""),
            *[str(value) for value in reversed(chunk.get("heading_path") or [])],
            str(chunk.get("document_archetype") or "").replace("_", " "),
        ]
        for candidate in candidates:
            tokens = [
                token
                for token in query_tokens(candidate)
                if len(token) >= 4 and token not in PREVIEW_STOPWORDS and not token.isdigit()
            ]
            if not tokens:
                continue
            query = " ".join(tokens[:3])
            if query in seen:
                continue
            seen.add(query)
            queries.append(query)
            if len(queries) >= limit:
                return queries

    return queries or ["documento"]


def build_retrieval_preview(chunks: Sequence[dict], *, ranking_profile: str = DEFAULT_RANKING_PROFILE) -> dict:
    normalized_profile = normalize_ranking_profile(ranking_profile)
    hydrated_chunks = [dict(chunk) for chunk in chunks]
    preview_queries = _default_preview_queries(hydrated_chunks)
    sample_queries: list[dict] = []
    sample_chunks_by_id: dict[str, dict] = {}

    for query in preview_queries:
        results = search_chunks(query, hydrated_chunks, limit=3, ranking_profile=normalized_profile)
        compact_results = [_compact_result(result) for result in results]
        if compact_results:
            sample_queries.append({"query": query, "results": compact_results})
        for result in compact_results:
            chunk_id = str(result.get("chunk_id") or "")
            if chunk_id and chunk_id not in sample_chunks_by_id:
                sample_chunks_by_id[chunk_id] = result

    if not sample_chunks_by_id:
        for chunk in hydrated_chunks[:10]:
            compact = _compact_result(
                {
                    **dict(chunk),
                    "score": 0,
                    "text_score": 0,
                    "vector_score": 0,
                    "retrieval_mode": "hybrid" if chunk.get("embedding") is not None else "textual",
                    "score_breakdown": {},
                    "text_score_breakdown": {},
                }
            )
            chunk_id = str(compact.get("chunk_id") or "")
            if chunk_id and chunk_id not in sample_chunks_by_id:
                sample_chunks_by_id[chunk_id] = compact

    embedding_count = sum(1 for chunk in hydrated_chunks if chunk.get("embedding") is not None)
    return {
        "artifact_role": "retrieval_preview",
        "mode": "hybrid_retrieval_ready" if embedding_count else "textual_retrieval_ready",
        "chunk_count": len(hydrated_chunks),
        "embedding_count": embedding_count,
        "ranking_profile": normalized_profile,
        "supported_filters": ["document_archetype", "file_name", "file_type"],
        "preview_queries": preview_queries,
        "sample_queries": sample_queries,
        "sample_chunks": list(sample_chunks_by_id.values())[:10],
    }
