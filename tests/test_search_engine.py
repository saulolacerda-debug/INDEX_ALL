from __future__ import annotations

from index_all.main import iter_supported_files, process_collection, process_file
from index_all.semantics.search_engine import search_collection, search_file

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
        assert top_result["locator"]["inciso"] == "Inciso I"
        assert top_result["score"] > 0


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


def test_search_file_searches_single_processed_output_dir():
    with workspace_test_dir() as temp_root:
        docx_path = create_legal_docx(temp_root / "norma.docx")
        output_dir = process_file(docx_path, temp_root / "saida")

        result = search_file("revogadas", output_dir, limit=5)

        assert result["results"]
        assert any(item["heading"].startswith("Art. 2º") for item in result["results"])
        assert all(item["file_name"] == "norma.docx" for item in result["results"])
