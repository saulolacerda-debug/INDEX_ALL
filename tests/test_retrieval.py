from __future__ import annotations

import json

from index_all.main import iter_supported_files, process_collection, process_file
from index_all.semantics.embedding_store import LocalEmbeddingStore
from index_all.semantics.retrieval import retrieve_context, search_chunks

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


def test_retrieve_context_returns_textual_results_without_embeddings():
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
        assert retrieval["mode"] == "textual"
        first_chunk = retrieval["chunks"][0]
        assert first_chunk["file_name"] == "manual.docx"
        assert first_chunk["document_archetype"] == "manual_procedural"
        assert first_chunk["heading_path"]
        assert first_chunk["heading_path_text"]
        assert first_chunk["locator"]["line_start"] is not None
        assert first_chunk["score_breakdown"]
        assert first_chunk["text_score"] > 0
        assert first_chunk["vector_score"] == 0
        assert first_chunk["retrieval_mode"] == "textual"
        assert "integridade" in retrieval["context_text"].lower()
        assert "manual.docx" in retrieval["context_text"]


def test_retrieve_context_uses_hybrid_scores_when_embeddings_exist():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        retrieval = retrieve_context("legalidade", collection_dir, filters={"document_archetype": "legislation_normative"}, limit=3)

        assert retrieval["chunks"]
        assert retrieval["mode"] == "hybrid"
        first_chunk = retrieval["chunks"][0]
        assert first_chunk["document_archetype"] == "legislation_normative"
        assert first_chunk["has_embedding"] is True
        assert first_chunk["vector_score"] > 0
        assert first_chunk["retrieval_mode"] == "hybrid"
        assert first_chunk["score_breakdown"]["vector"] > 0


def test_collection_outputs_include_embeddings_and_enriched_retrieval_preview():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        search_index = json.loads((collection_dir / "search_index.json").read_text(encoding="utf-8"))
        chunks_payload = json.loads((collection_dir / "chunks.json").read_text(encoding="utf-8"))
        embeddings_payload = json.loads((collection_dir / "embeddings_index.json").read_text(encoding="utf-8"))
        retrieval_preview = json.loads((collection_dir / "retrieval_preview.json").read_text(encoding="utf-8"))
        collection_metadata = json.loads((collection_dir / "collection_metadata.json").read_text(encoding="utf-8"))
        collection_summary = (collection_dir / "collection_summary.md").read_text(encoding="utf-8")
        collection_report = (collection_dir / "collection_report.html").read_text(encoding="utf-8")

        assert search_index["metadata"]["artifact_role"] == "collection_search_index"
        assert search_index["metadata"]["record_count"] > 0
        assert chunks_payload["artifact_role"] == "local_embedding_store"
        assert chunks_payload["chunk_count"] > 0
        assert chunks_payload["metadata"]["embedding_count"] == chunks_payload["chunk_count"]
        assert chunks_payload["metadata"]["embedding_state"] == "ready"
        assert embeddings_payload["artifact_role"] == "local_embeddings_index"
        assert embeddings_payload["metadata"]["embedding_count"] == embeddings_payload["chunk_count"]
        assert embeddings_payload["metadata"]["embedding_state"] == "ready"
        assert retrieval_preview["artifact_role"] == "retrieval_preview"
        assert retrieval_preview["mode"] == "hybrid_retrieval_ready"
        assert retrieval_preview["ranking_profile"] == "legal"
        assert retrieval_preview["chunk_count"] == chunks_payload["chunk_count"]
        assert retrieval_preview["sample_chunks"][0]["score"] >= 0
        assert retrieval_preview["sample_chunks"][0]["score_breakdown"]
        assert retrieval_preview["sample_chunks"][0]["text_score"] >= 0
        assert retrieval_preview["sample_chunks"][0]["vector_score"] >= 0
        assert retrieval_preview["sample_chunks"][0]["preview_text"]
        assert retrieval_preview["sample_queries"]
        assert collection_metadata["semantic"]["embeddings"]["embedding_count"] == embeddings_payload["chunk_count"]
        assert "Chunks com embedding persistido" in collection_summary
        assert "Modo de retrieval" in collection_summary
        assert "Embeddings persistidos" in collection_report
        assert "Preview De Retrieval" in collection_report
        assert "Preview Por Query" in collection_report


def test_exact_legal_reference_query_prioritizes_art_156_a_over_art_156():
    with workspace_test_dir() as temp_root:
        store = LocalEmbeddingStore(temp_root / "colecao")
        chunks = [
            {
                "chunk_id": "chunk_001",
                "source_kind": "chunk",
                "file_name": "norma.pdf",
                "file_type": "pdf",
                "document_archetype": "legislation_normative",
                "heading": "Art. 156 - Disposição geral do IBS",
                "heading_path": ["Título I", "Art. 156 - Disposição geral do IBS"],
                "heading_path_text": "Título I > Art. 156 - Disposição geral do IBS",
                "text": "Art. 156 dispõe sobre regras gerais do IBS.",
                "locator": {"article": "Art. 156"},
                "metadata": {"text_length": 44},
            },
            {
                "chunk_id": "chunk_002",
                "source_kind": "chunk",
                "file_name": "norma.pdf",
                "file_type": "pdf",
                "document_archetype": "legislation_normative",
                "heading": "Art. 156-A - Imposto sobre Bens e Serviços (IBS)",
                "heading_path": ["Título I", "Art. 156-A - Imposto sobre Bens e Serviços (IBS)"],
                "heading_path_text": "Título I > Art. 156-A - Imposto sobre Bens e Serviços (IBS)",
                "text": "Art. 156-A institui o IBS e disciplina sua competência compartilhada.",
                "locator": {"article": "Art. 156-A"},
                "metadata": {"text_length": 66},
            },
        ]

        embedding_payload = store.build_embeddings(chunks)
        hydrated_chunks = store.hydrate_chunks(chunks, embedding_payload=embedding_payload)
        results = search_chunks("art. 156-a ibs", hydrated_chunks, limit=2)

        assert [item["chunk_id"] for item in results] == ["chunk_002", "chunk_001"]
        assert results[0]["vector_score"] > 0
        assert results[0]["score_breakdown"]["legal_reference"] > 0
        assert results[1]["score_breakdown"]["legal_reference"] == 0
