from __future__ import annotations

import json

from index_all.main import iter_supported_files, process_collection, process_file
from index_all.semantics.embedding_store import LocalEmbeddingStore

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


def test_embedding_store_builds_persists_and_reuses_embeddings():
    with workspace_test_dir() as temp_root:
        store = LocalEmbeddingStore(temp_root / "colecao")
        chunks = [
            {
                "chunk_id": "chunk_00001",
                "source_kind": "chunk",
                "file_name": "norma.docx",
                "file_type": "docx",
                "document_archetype": "legislation_normative",
                "heading": "Art. 1º",
                "heading_path": ["Art. 1º"],
                "heading_path_text": "Art. 1º",
                "text": "Esta lei estabelece legalidade, neutralidade e segurança jurídica.",
                "locator": {"article": "Art. 1º"},
                "metadata": {"text_length": 69},
            }
        ]

        payload = store.build_embeddings(chunks)
        chunk_payload = store.save_chunks(chunks, embedding_payload=payload)
        reloaded = store.load_embeddings_payload()
        reused = store.build_embeddings(chunks)

        assert payload["artifact_role"] == "local_embeddings_index"
        assert payload["metadata"]["embedding_count"] == 1
        assert payload["metadata"]["embedding_state"] == "ready"
        assert payload["records"][0]["chunk_id"] == "chunk_00001"
        assert payload["records"][0]["file_name"] == "norma.docx"
        assert payload["records"][0]["document_archetype"] == "legislation_normative"
        assert payload["records"][0]["heading_path_text"] == "Art. 1º"
        assert payload["records"][0]["locator"]["article"] == "Art. 1º"
        assert payload["records"][0]["vector"]
        assert chunk_payload["records"][0]["embedding"]
        assert reloaded["metadata"]["embedding_count"] == 1
        assert reused["metadata"]["reused_count"] == 1
        assert reused["metadata"]["built_count"] == 0


def test_collection_summary_and_metadata_reflect_persisted_embeddings():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        collection_metadata = json.loads((collection_dir / "collection_metadata.json").read_text(encoding="utf-8"))
        collection_summary = (collection_dir / "collection_summary.md").read_text(encoding="utf-8")

        assert collection_metadata["available_artifacts"]["embeddings_index"] == "embeddings_index.json"
        assert collection_metadata["semantic"]["embeddings"]["embedding_count"] > 0
        assert collection_metadata["semantic"]["embeddings"]["embedding_state"] == "ready"
        assert "Chunks com embedding persistido" in collection_summary
