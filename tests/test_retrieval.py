from __future__ import annotations

import json

from index_all.main import iter_supported_files, process_collection, process_file
from index_all.semantics.retrieval import retrieve_context

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


def test_retrieve_context_returns_ranked_chunks_with_prompt_ready_context():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        retrieval = retrieve_context("integridade", collection_dir, filters={"document_archetype": "manual_procedural"}, limit=3)

        assert retrieval["chunks"]
        first_chunk = retrieval["chunks"][0]
        assert first_chunk["file_name"] == "manual.docx"
        assert first_chunk["document_archetype"] == "manual_procedural"
        assert first_chunk["heading_path"]
        assert first_chunk["locator"]["line_start"] is not None
        assert "integridade" in retrieval["context_text"].lower()
        assert "manual.docx" in retrieval["context_text"]


def test_collection_outputs_include_search_index_chunks_and_retrieval_preview():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        search_index = json.loads((collection_dir / "search_index.json").read_text(encoding="utf-8"))
        chunks_payload = json.loads((collection_dir / "chunks.json").read_text(encoding="utf-8"))
        retrieval_preview = json.loads((collection_dir / "retrieval_preview.json").read_text(encoding="utf-8"))
        collection_summary = (collection_dir / "collection_summary.md").read_text(encoding="utf-8")
        collection_report = (collection_dir / "collection_report.html").read_text(encoding="utf-8")

        assert search_index["metadata"]["artifact_role"] == "collection_search_index"
        assert search_index["metadata"]["record_count"] > 0
        assert chunks_payload["artifact_role"] == "local_embedding_store"
        assert chunks_payload["chunk_count"] > 0
        assert retrieval_preview["artifact_role"] == "retrieval_preview"
        assert retrieval_preview["chunk_count"] == chunks_payload["chunk_count"]
        assert "## Busca E Chunks" in collection_summary
        assert "Search Index" in collection_report
        assert "Busca E Chunks" in collection_report
