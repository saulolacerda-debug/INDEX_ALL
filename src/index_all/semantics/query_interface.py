from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from index_all.indexing.collection_summary_builder import build_collection_summary
from index_all.outputs.html_writer import write_collection_report_html
from index_all.outputs.json_writer import read_json, write_json
from index_all.outputs.markdown_writer import write_collection_summary_markdown
from index_all.semantics.chunker import build_collection_chunks
from index_all.semantics.embedding_store import LocalEmbeddingStore
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
) -> dict:
    resolved_dir = Path(collection_dir)
    store = LocalEmbeddingStore(resolved_dir)
    chunks = ensure_collection_chunks(resolved_dir)
    payload = store.build_embeddings(chunks, force=force)
    store.save_chunks(chunks, embedding_payload=payload)
    refresh_collection_outputs(resolved_dir)
    return payload


def refresh_collection_outputs(
    collection_dir: str | Path,
    *,
    query_results: Mapping[str, Any] | None = None,
) -> dict:
    resolved_dir = Path(collection_dir)
    store = LocalEmbeddingStore(resolved_dir)

    collection_metadata = dict(read_json(resolved_dir / "collection_metadata.json"))
    catalog = list(read_json(resolved_dir / "catalog.json"))
    master_index = list(read_json(resolved_dir / "master_index.json"))

    chunks = ensure_collection_chunks(resolved_dir)
    embedding_payload = store.load_embeddings_payload()
    chunk_payload = store.save_chunks(chunks, embedding_payload=embedding_payload)
    retrieval_preview = build_retrieval_preview(chunk_payload.get("records", []) or [])
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

    resolved_query_results: Mapping[str, Any] | None = query_results
    query_results_path = resolved_dir / "query_results.json"
    if resolved_query_results is None and query_results_path.exists():
        resolved_query_results = read_json(query_results_path)
    if resolved_query_results:
        preview_results = list(resolved_query_results.get("chunks", []) or [])[:5]
        semantic["query_results"] = {
            "query": resolved_query_results.get("query"),
            "total_hits": len(list(resolved_query_results.get("chunks", []) or [])),
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
        collection_metadata.setdefault("available_artifacts", {})["query_results"] = "query_results.json"

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
    write_collection_summary_markdown(resolved_dir / "collection_summary.md", collection_payload)
    write_collection_report_html(resolved_dir / "collection_report.html", collection_payload)
    return collection_payload


def query_collection(
    collection_dir: str | Path,
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    limit: int = 6,
    write_results_file: bool = False,
) -> dict:
    resolved_dir = Path(collection_dir)
    results = retrieve_context(query, resolved_dir, filters=filters, limit=limit)
    payload = {
        "artifact_role": "query_results",
        **results,
    }
    if write_results_file:
        write_json(resolved_dir / "query_results.json", payload)
        refresh_collection_outputs(resolved_dir, query_results=payload)
    return payload


def format_query_results_for_console(result: Mapping[str, Any]) -> str:
    lines = [f'Consulta: "{result.get("query", "")}"']
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
