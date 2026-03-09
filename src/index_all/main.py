from __future__ import annotations

import argparse
import json
from pathlib import Path

from index_all.config import get_settings
from index_all.indexing.catalog_builder import build_catalog
from index_all.indexing.collection_summary_builder import build_collection_metadata, build_collection_summary
from index_all.indexing.consultation_payload import (
    build_ai_context_payload,
    build_content_payload,
    build_index_payload,
    build_metadata_payload,
)
from index_all.indexing.document_classifier import classify_document_archetype
from index_all.indexing.master_index_builder import build_master_index
from index_all.indexing.metadata_extractor import extract_common_metadata
from index_all.indexing.structure_indexer import build_structure_index
from index_all.indexing.summary_builder import build_summary
from index_all.ingestion.file_router import get_parser_for_path, is_ignored_path
from index_all.outputs.html_writer import write_collection_report_html, write_report_html
from index_all.outputs.json_writer import write_json, write_json_bundle
from index_all.outputs.markdown_writer import (
    write_ai_context_markdown,
    write_collection_summary_markdown,
    write_summary_markdown,
)
from index_all.semantics.chunker import build_collection_chunks
from index_all.semantics.embedding_store import LocalEmbeddingStore
from index_all.semantics.retrieval import build_retrieval_preview
from index_all.semantics.search_engine import build_search_index
from index_all.utils.logging_utils import configure_logging, get_logger
from index_all.utils.paths import ensure_dir, unique_output_dir


logger = get_logger(__name__)


def _contains_only_ignored_files(input_path: Path) -> bool:
    if not input_path.is_dir():
        return False

    seen_file = False
    for path in input_path.rglob("*"):
        if not path.is_file():
            continue
        seen_file = True
        if not is_ignored_path(path):
            return False
    return seen_file


def iter_supported_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if is_ignored_path(input_path):
            return []
        return [input_path]

    files = []
    for path in input_path.rglob("*"):
        if path.is_file() and not is_ignored_path(path):
            files.append(path)
    return sorted(files)


def process_file(file_path: Path, output_root: Path) -> Path:
    parser = get_parser_for_path(file_path)
    parsed = parser(file_path)

    metadata = extract_common_metadata(file_path)
    content = parsed.get("content", {"blocks": [], "parser_metadata": {}})
    blocks = content.get("blocks", [])
    parser_metadata = content.get("parser_metadata", {})
    document_archetype = classify_document_archetype(metadata, blocks, parser_metadata)
    metadata = {**metadata, "document_archetype": document_archetype}
    index_entries = build_structure_index(blocks, document_archetype=document_archetype)
    summary = build_summary(metadata, blocks, index_entries)
    consultation_payload = build_content_payload(
        metadata,
        content,
        index_entries,
        summary,
        document_archetype=document_archetype,
    )
    metadata_payload = build_metadata_payload(metadata, consultation_payload)
    index_payload = build_index_payload(metadata, consultation_payload)
    ai_context_payload = build_ai_context_payload(metadata_payload, consultation_payload, index_payload)

    output_dir = unique_output_dir(output_root, file_path.stem)

    write_json(output_dir / "ai_context.json", ai_context_payload)
    write_json(output_dir / "metadata.json", metadata_payload)
    write_json(output_dir / "content.json", consultation_payload)
    write_json(output_dir / "index.json", index_payload)
    write_ai_context_markdown(output_dir / "ai_context.md", ai_context_payload)
    write_summary_markdown(output_dir / "summary.md", consultation_payload)
    write_report_html(output_dir / "report.html", metadata, consultation_payload, index_entries, summary)

    logger.info("Processed %s -> %s", file_path.name, output_dir)
    return output_dir


def _load_processed_document(output_dir: Path) -> dict:
    return {
        "metadata": json.loads((output_dir / "metadata.json").read_text(encoding="utf-8")),
        "content": json.loads((output_dir / "content.json").read_text(encoding="utf-8")),
        "index": json.loads((output_dir / "index.json").read_text(encoding="utf-8")),
        "output_dir": str(output_dir.resolve()),
    }


def process_collection(
    source_dir: Path,
    output_root: Path,
    processed_output_dirs: list[Path],
    *,
    build_search: bool = True,
    build_chunks: bool = True,
) -> Path:
    processed_documents = [_load_processed_document(output_dir) for output_dir in processed_output_dirs]
    catalog = build_catalog(processed_documents)
    master_index = build_master_index(processed_documents)
    collection_metadata = build_collection_metadata(source_dir, catalog, master_index)
    collection_summary = build_collection_summary(collection_metadata, catalog, master_index)
    semantic_payload: dict = {}
    collection_payload = {
        "metadata": collection_metadata,
        "catalog": catalog,
        "master_index": master_index,
        "summary": collection_summary,
    }

    collection_dir = unique_output_dir(output_root, f"{source_dir.name}_collection")
    json_payloads: dict[str, dict | list] = {
        "collection_metadata.json": collection_metadata,
        "catalog.json": catalog,
        "master_index.json": master_index,
    }

    if build_chunks:
        chunk_store = LocalEmbeddingStore(collection_dir / "chunks.json")
        chunk_payload = chunk_store.save_chunks(build_collection_chunks(processed_documents))
        retrieval_preview = build_retrieval_preview(chunk_payload.get("records", []) or [])
        json_payloads["chunks.json"] = chunk_payload
        json_payloads["retrieval_preview.json"] = retrieval_preview
        semantic_payload["chunks"] = {
            "chunk_count": chunk_payload.get("chunk_count", 0),
            "metadata": dict(chunk_payload.get("metadata", {}) or {}),
            "sample_headings": [
                chunk.get("heading_path_text")
                for chunk in (chunk_payload.get("records", []) or [])[:10]
                if chunk.get("heading_path_text")
            ],
        }
        semantic_payload["retrieval_preview"] = retrieval_preview
        collection_metadata.setdefault("available_artifacts", {})["chunks"] = "chunks.json"
        collection_metadata.setdefault("available_artifacts", {})["retrieval_preview"] = "retrieval_preview.json"

    if build_search:
        search_index = build_search_index(processed_documents, catalog, master_index)
        json_payloads["search_index.json"] = search_index
        semantic_payload["search"] = {
            **dict(search_index.get("metadata", {}) or {}),
        }
        collection_metadata.setdefault("available_artifacts", {})["search_index"] = "search_index.json"

    collection_payload["semantic"] = semantic_payload
    json_payloads["collection_metadata.json"] = collection_metadata

    write_json_bundle(collection_dir, json_payloads)
    write_collection_summary_markdown(collection_dir / "collection_summary.md", collection_payload)
    write_collection_report_html(collection_dir / "collection_report.html", collection_payload)

    logger.info("Built collection %s -> %s", source_dir.name, collection_dir)
    return collection_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="INDEX_ALL - universal file indexer")
    parser.add_argument("input_path", help="Path to a file or directory")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to data/processed",
    )
    parser.add_argument(
        "--build-search",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Build search_index.json for collection outputs. Defaults to enabled for directory inputs.",
    )
    parser.add_argument(
        "--build-chunks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Build chunks.json for collection outputs. Defaults to enabled for directory inputs.",
    )
    return parser


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    settings = get_settings()
    output_root = Path(args.output_dir).resolve() if args.output_dir else settings.processed_dir
    ensure_dir(output_root)

    files = iter_supported_files(input_path)
    if not files:
        if input_path.is_file() and is_ignored_path(input_path):
            return
        if _contains_only_ignored_files(input_path):
            return
        logger.warning("No files found in %s", input_path)
        return

    supported = 0
    skipped = 0
    processed_output_dirs: list[Path] = []
    for file_path in files:
        try:
            output_dir = process_file(file_path, output_root)
            supported += 1
            processed_output_dirs.append(output_dir)
        except ValueError as exc:
            skipped += 1
            logger.warning("Skipping %s: %s", file_path, exc)
        except Exception as exc:  # pragma: no cover
            skipped += 1
            logger.exception("Failed processing %s: %s", file_path, exc)

    if input_path.is_dir() and processed_output_dirs:
        process_collection(
            input_path,
            output_root,
            processed_output_dirs,
            build_search=True if args.build_search is None else bool(args.build_search),
            build_chunks=True if args.build_chunks is None else bool(args.build_chunks),
        )

    logger.info("Done. Supported=%s | Skipped=%s", supported, skipped)


if __name__ == "__main__":
    main()
