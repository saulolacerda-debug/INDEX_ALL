from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from index_all.indexing.collection_summary_builder import build_collection_summary
from index_all.outputs.html_writer import write_collection_report_html
from index_all.outputs.json_writer import read_json, write_json
from index_all.outputs.markdown_writer import (
    write_answer_results_markdown,
    write_collection_summary_markdown,
)
from index_all.semantics.answering import generate_answer_payload
from index_all.semantics.chunker import build_collection_chunks
from index_all.semantics.embedding_store import LocalEmbeddingStore
from index_all.semantics.ranking_profiles import DEFAULT_RANKING_PROFILE, normalize_ranking_profile
from index_all.semantics.retrieval import build_retrieval_preview, retrieve_context
from index_all.semantics.search_engine import load_processed_document


def ensure_collection_chunks(collection_dir: str | Path) -> list[dict]:
    resolved_dir = Path(collection_dir)
    store = LocalEmbeddingStore(resolved_dir)
    chunks = store.load_chunks()
    if chunks:
        return chunks

    catalog = list(read_json(resolved_dir / "catalog.json"))
    processed_documents = [load_processed_document(entry["output_dir"]) for entry in catalog]
    chunks = build_collection_chunks(processed_documents)
    store.save_chunks(chunks)
    return chunks


def build_embeddings_for_collection(
    collection_dir: str | Path,
    *,
    force: bool = False,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> dict:
    resolved_dir = Path(collection_dir)
    store = LocalEmbeddingStore(resolved_dir)
    chunks = ensure_collection_chunks(resolved_dir)
    payload = store.build_embeddings(chunks, force=force)
    store.save_chunks(chunks, embedding_payload=payload)
    refresh_collection_outputs(resolved_dir, ranking_profile=ranking_profile)
    return payload


def _query_semantic_preview(results: Mapping[str, Any]) -> dict:
    preview_results = list(results.get("chunks", []) or [])[:5]
    return {
        "query": results.get("query"),
        "total_hits": len(list(results.get("chunks", []) or [])),
        "mode": results.get("mode"),
        "ranking_profile": results.get("ranking_profile"),
        "results": [
            {
                "file_name": item.get("file_name"),
                "document_archetype": item.get("document_archetype"),
                "heading_path_text": item.get("heading_path_text"),
                "score": item.get("score"),
                "locator_path": item.get("locator_path") or item.get("position_text"),
            }
            for item in preview_results
        ],
    }


def _answer_semantic_preview(answer_results: Mapping[str, Any]) -> dict:
    answer_text = str(answer_results.get("answer_text") or "").strip()
    preview = answer_text if len(answer_text) <= 320 else f"{answer_text[:317].rstrip()}..."
    citations = list(answer_results.get("citations", []) or [])
    return {
        "query": answer_results.get("query"),
        "status": answer_results.get("status"),
        "mode": answer_results.get("mode"),
        "ranking_profile": answer_results.get("ranking_profile"),
        "provider": answer_results.get("provider"),
        "deployment": answer_results.get("deployment"),
        "response_id": answer_results.get("response_id"),
        "citation_count": len(citations),
        "answer_preview": preview,
        "citations": [
            {
                "id": item.get("id"),
                "reference": item.get("reference"),
            }
            for item in citations[:5]
        ],
    }


def refresh_collection_outputs(
    collection_dir: str | Path,
    *,
    query_results: Mapping[str, Any] | None = None,
    answer_results: Mapping[str, Any] | None = None,
    ranking_profile: str | None = None,
) -> dict:
    resolved_dir = Path(collection_dir)
    store = LocalEmbeddingStore(resolved_dir)

    collection_metadata = dict(read_json(resolved_dir / "collection_metadata.json"))
    catalog = list(read_json(resolved_dir / "catalog.json"))
    master_index = list(read_json(resolved_dir / "master_index.json"))

    resolved_query_results: Mapping[str, Any] | None = query_results
    query_results_path = resolved_dir / "query_results.json"
    if resolved_query_results is None and query_results_path.exists():
        resolved_query_results = read_json(query_results_path)

    resolved_answer_results: Mapping[str, Any] | None = answer_results
    answer_results_path = resolved_dir / "answer_results.json"
    if resolved_answer_results is None and answer_results_path.exists():
        resolved_answer_results = read_json(answer_results_path)

    resolved_ranking_profile = normalize_ranking_profile(
        ranking_profile
        or (resolved_answer_results or {}).get("ranking_profile")
        or (resolved_query_results or {}).get("ranking_profile")
        or DEFAULT_RANKING_PROFILE
    )

    chunks = ensure_collection_chunks(resolved_dir)
    embedding_payload = store.load_embeddings_payload()
    chunk_payload = store.save_chunks(chunks, embedding_payload=embedding_payload)
    retrieval_preview = build_retrieval_preview(
        chunk_payload.get("records", []) or [],
        ranking_profile=resolved_ranking_profile,
    )
    write_json(resolved_dir / "retrieval_preview.json", retrieval_preview)

    semantic: dict[str, Any] = {}
    search_index_path = resolved_dir / "search_index.json"
    if search_index_path.exists():
        search_index = read_json(search_index_path)
        semantic["search"] = dict(search_index.get("metadata", {}) or {})
        collection_metadata.setdefault("available_artifacts", {})["search_index"] = "search_index.json"

    semantic["chunks"] = {
        "chunk_count": chunk_payload.get("chunk_count", 0),
        "metadata": dict(chunk_payload.get("metadata", {}) or {}),
        "sample_headings": [
            chunk.get("heading_path_text")
            for chunk in (chunk_payload.get("records", []) or [])[:10]
            if chunk.get("heading_path_text")
        ],
    }
    semantic["embeddings"] = {
        "chunk_count": embedding_payload.get("chunk_count", 0),
        **dict(embedding_payload.get("metadata", {}) or {}),
    }
    semantic["retrieval_preview"] = retrieval_preview

    collection_metadata.setdefault("available_artifacts", {})["chunks"] = "chunks.json"
    collection_metadata.setdefault("available_artifacts", {})["embeddings_index"] = "embeddings_index.json"
    collection_metadata.setdefault("available_artifacts", {})["retrieval_preview"] = "retrieval_preview.json"

    if resolved_query_results:
        semantic["query_results"] = _query_semantic_preview(resolved_query_results)
        collection_metadata.setdefault("available_artifacts", {})["query_results"] = "query_results.json"

    if resolved_answer_results:
        semantic["answer_results"] = _answer_semantic_preview(resolved_answer_results)
        collection_metadata.setdefault("available_artifacts", {})["answer_results"] = "answer_results.json"
        collection_metadata.setdefault("available_artifacts", {})["answer_results_markdown"] = "answer_results.md"

    collection_metadata["semantic"] = semantic
    summary = build_collection_summary(collection_metadata, catalog, master_index)
    collection_payload = {
        "metadata": collection_metadata,
        "catalog": catalog,
        "master_index": master_index,
        "summary": summary,
        "semantic": semantic,
    }

    write_json(resolved_dir / "collection_metadata.json", collection_metadata)
    write_json(resolved_dir / "chunks.json", chunk_payload)
    write_json(resolved_dir / "embeddings_index.json", embedding_payload)
    if resolved_query_results:
        write_json(resolved_dir / "query_results.json", dict(resolved_query_results))
    if resolved_answer_results:
        write_json(resolved_dir / "answer_results.json", dict(resolved_answer_results))
        write_answer_results_markdown(resolved_dir / "answer_results.md", dict(resolved_answer_results))
    write_collection_summary_markdown(resolved_dir / "collection_summary.md", collection_payload)
    write_collection_report_html(resolved_dir / "collection_report.html", collection_payload)
    return collection_payload


def query_collection(
    collection_dir: str | Path,
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    limit: int = 6,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
    write_results_file: bool = False,
) -> dict:
    resolved_dir = Path(collection_dir)
    normalized_profile = normalize_ranking_profile(ranking_profile)
    results = retrieve_context(
        query,
        resolved_dir,
        filters=filters,
        limit=limit,
        ranking_profile=normalized_profile,
    )
    payload = {
        "artifact_role": "query_results",
        **results,
    }
    if write_results_file:
        write_json(resolved_dir / "query_results.json", payload)
        refresh_collection_outputs(
            resolved_dir,
            query_results=payload,
            ranking_profile=normalized_profile,
        )
    return payload


def answer_collection(
    collection_dir: str | Path,
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    limit: int = 6,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
    write_results_file: bool = False,
    client_factory: Callable[[Any], Any] | None = None,
) -> dict:
    resolved_dir = Path(collection_dir)
    normalized_profile = normalize_ranking_profile(ranking_profile)
    query_results = query_collection(
        resolved_dir,
        query,
        filters=filters,
        limit=limit,
        ranking_profile=normalized_profile,
        write_results_file=False,
    )
    answer_results = generate_answer_payload(
        query_results,
        client_factory=client_factory,
    )
    if write_results_file:
        write_json(resolved_dir / "query_results.json", query_results)
        write_json(resolved_dir / "answer_results.json", answer_results)
        write_answer_results_markdown(resolved_dir / "answer_results.md", answer_results)
        refresh_collection_outputs(
            resolved_dir,
            query_results=query_results,
            answer_results=answer_results,
            ranking_profile=normalized_profile,
        )
    return answer_results


def format_query_results_for_console(result: Mapping[str, Any]) -> str:
    lines = [f'Consulta: "{result.get("query", "")}"']
    ranking_profile = str(result.get("ranking_profile") or "").strip()
    if ranking_profile:
        lines.append(f"Perfil de ranking: {ranking_profile}")
    filters = dict(result.get("filters", {}) or {})
    if filters:
        filter_text = ", ".join(f"{key}={value}" for key, value in filters.items() if value not in (None, "", []))
        if filter_text:
            lines.append(f"Filtros: {filter_text}")

    chunks = list(result.get("chunks", []) or [])
    if not chunks:
        lines.append("Nenhum resultado encontrado.")
        return "\n".join(lines)

    for index, chunk in enumerate(chunks, start=1):
        heading = str(chunk.get("heading_path_text") or chunk.get("heading") or "")
        locator = str(chunk.get("locator_path") or chunk.get("position_text") or "")
        lines.append(
            f"{index}. {chunk.get('file_name')} | {chunk.get('document_archetype')} | "
            f"score={chunk.get('score')} | text={chunk.get('text_score')} | vector={chunk.get('vector_score')}"
        )
        if heading:
            lines.append(f"   {heading}")
        if locator:
            lines.append(f"   {locator}")
        snippet = str(chunk.get("snippet") or "").strip()
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


def format_answer_results_for_console(result: Mapping[str, Any]) -> str:
    lines = [f'Consulta: "{result.get("query", "")}"']
    lines.append(f"Status: {result.get('status', 'unknown')}")
    ranking_profile = str(result.get("ranking_profile") or "").strip()
    if ranking_profile:
        lines.append(f"Perfil de ranking: {ranking_profile}")
    provider = str(result.get("provider") or "").strip()
    deployment = str(result.get("deployment") or "").strip()
    if provider:
        lines.append(f"Provider: {provider}")
    if deployment:
        lines.append(f"Deployment: {deployment}")
    response_id = str(result.get("response_id") or "").strip()
    if response_id:
        lines.append(f"Response ID: {response_id}")

    answer_text = str(result.get("answer_text") or "").strip()
    if answer_text:
        lines.extend(["", answer_text])

    citations = list(result.get("citations", []) or [])
    if citations:
        lines.extend(["", "Citações:"])
        for item in citations:
            lines.append(f"  [{item.get('id')}] {item.get('reference')}")
    return "\n".join(lines)
