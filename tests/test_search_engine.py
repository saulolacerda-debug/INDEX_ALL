from __future__ import annotations

import json

from index_all.main import build_parser, iter_supported_files, process_collection, process_file
from index_all.semantics.search_engine import score_text_match, search_collection, search_file

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


def test_search_collection_returns_hits_with_heading_and_locator():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        result = search_collection("legalidade", collection_dir=collection_dir, limit=5)

        assert result["results"]
        top_result = result["results"][0]
        assert top_result["file_name"] == "norma.docx"
        assert top_result["document_archetype"] == "legislation_normative"
        assert top_result["heading"]
        assert top_result["heading_path_text"]
        assert top_result["locator"]["inciso"] == "Inciso I"
        assert top_result["score"] > 0
        assert top_result["score_breakdown"]


def test_search_collection_supports_archetype_filter():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        result = search_collection(
            "arquivo",
            collection_dir=collection_dir,
            filters={"document_archetype": "manual_procedural"},
            limit=5,
        )

        assert result["results"]
        assert {item["document_archetype"] for item in result["results"]} == {"manual_procedural"}
        assert all(item["file_name"] == "manual.docx" for item in result["results"])
        assert all(item["heading_path_text"] for item in result["results"])


def test_search_file_searches_single_processed_output_dir():
    with workspace_test_dir() as temp_root:
        docx_path = create_legal_docx(temp_root / "norma.docx")
        output_dir = process_file(docx_path, temp_root / "saida")

        result = search_file("revogadas", output_dir, limit=5)

        assert result["results"]
        assert any(item["heading"].startswith("Art. 2º") for item in result["results"])
        assert all(item["file_name"] == "norma.docx" for item in result["results"])


def test_search_index_deduplicates_redundant_records():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        search_index = json.loads((collection_dir / "search_index.json").read_text(encoding="utf-8"))
        metadata = search_index["metadata"]

        assert metadata["raw_record_count"] > metadata["record_count"]
        assert metadata["exact_duplicates_removed"] + metadata["near_duplicates_removed"] > 0


def test_search_collection_supports_file_name_filter():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        result = search_collection(
            "arquivo",
            collection_dir=collection_dir,
            filters={"file_name": "manual.docx"},
            limit=5,
        )

        assert result["results"]
        assert {item["file_name"] for item in result["results"]} == {"manual.docx"}


def test_cli_help_mentions_hybrid_retrieval_options():
    help_text = build_parser().format_help()

    assert "--build-embeddings" in help_text
    assert "--query" in help_text
    assert "--limit" in help_text
    assert "--archetype" in help_text
    assert "--file-name" in help_text


def test_score_text_match_prioritizes_exact_legal_reference_with_suffix():
    exact = score_text_match(
        "art. 156-a ibs",
        title="Art. 156-A - Imposto sobre Bens e Serviços (IBS)",
        heading_path=["Título I", "Art. 156-A - Imposto sobre Bens e Serviços (IBS)"],
        text="Art. 156-A institui o IBS.",
        file_name="norma.pdf",
        document_archetype="legislation_normative",
        source_kind="chunk",
    )
    partial = score_text_match(
        "art. 156-a ibs",
        title="Art. 156 - Regras gerais do IBS",
        heading_path=["Título I", "Art. 156 - Regras gerais do IBS"],
        text="Art. 156 trata de disposições gerais do IBS.",
        file_name="norma.pdf",
        document_archetype="legislation_normative",
        source_kind="chunk",
    )

    assert exact["score"] > partial["score"]
    assert exact["score_breakdown"]["legal_ref_title_exact"] > 0
    assert partial["score"] == 0
