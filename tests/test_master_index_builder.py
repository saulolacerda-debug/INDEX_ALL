from __future__ import annotations

import json

from index_all.indexing.master_index_builder import build_master_index
from index_all.main import iter_supported_files, process_collection, process_file

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


def _sample_processed_documents() -> list[dict]:
    return [
        {
            "metadata": {"file_name": "norma.docx", "file_type": "docx", "document_archetype": "legislation_normative"},
            "content": {
                "document_archetype": "legislation_normative",
                "blocks": [{"id": "block_0001"}, {"id": "block_0002"}],
                "document_profile": {"block_count": 2, "index_entry_count": 2},
            },
            "index": [
                {
                    "id": "idx_0001",
                    "title": "Parte Geral",
                    "kind": "part",
                    "level": 2,
                    "parent_id": None,
                    "children": [
                        {
                            "id": "idx_0002",
                            "title": "Art. 1º",
                            "kind": "article",
                            "level": 8,
                            "parent_id": "idx_0001",
                            "children": [],
                        }
                    ],
                }
            ],
            "output_dir": "saida\\norma",
        },
        {
            "metadata": {"file_name": "manual.docx", "file_type": "docx", "document_archetype": "manual_procedural"},
            "content": {
                "document_archetype": "manual_procedural",
                "blocks": [{"id": "block_0001"}],
                "document_profile": {"block_count": 1, "index_entry_count": 1},
            },
            "index": [
                {"id": "idx_0001", "title": "MANUAL", "kind": "heading", "level": 1, "parent_id": None, "children": []}
            ],
            "output_dir": "saida\\manual",
        },
    ]


def test_build_master_index_preserves_per_file_hierarchy_with_namespaced_ids():
    master_index = build_master_index(_sample_processed_documents())

    assert len(master_index) == 2
    assert master_index[0]["kind"] == "document"
    assert master_index[0]["title"] == "norma.docx"
    assert master_index[0]["children"][0]["id"].startswith("master_0001_")
    assert master_index[0]["children"][0]["parent_id"] == "master_0001"
    assert master_index[0]["children"][0]["level"] == 3
    assert master_index[0]["children"][0]["children"][0]["parent_id"] == master_index[0]["children"][0]["id"]
    assert master_index[1]["document_archetype"] == "manual_procedural"


def test_process_collection_writes_consolidated_outputs_without_breaking_file_outputs():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs)

        assert all((output_dir / "content.json").exists() for output_dir in processed_output_dirs)
        assert (collection_dir / "collection_metadata.json").exists()
        assert (collection_dir / "catalog.json").exists()
        assert (collection_dir / "master_index.json").exists()
        assert (collection_dir / "search_index.json").exists()
        assert (collection_dir / "chunks.json").exists()
        assert (collection_dir / "collection_summary.md").exists()
        assert (collection_dir / "collection_report.html").exists()

        catalog = json.loads((collection_dir / "catalog.json").read_text(encoding="utf-8"))
        master_index = json.loads((collection_dir / "master_index.json").read_text(encoding="utf-8"))
        collection_metadata = json.loads((collection_dir / "collection_metadata.json").read_text(encoding="utf-8"))
        collection_summary = (collection_dir / "collection_summary.md").read_text(encoding="utf-8")
        collection_report = (collection_dir / "collection_report.html").read_text(encoding="utf-8")

        assert len(catalog) == 2
        assert {entry["document_archetype"] for entry in catalog} == {"legislation_normative", "manual_procedural"}
        assert [node["title"] for node in master_index] == ["manual.docx", "norma.docx"]
        assert collection_metadata["file_count"] == 2
        assert "## Catálogo Do Acervo" in collection_summary
        assert "## Índice Mestre" in collection_summary
        assert "INDEX_ALL Collection Report" in collection_report
        assert "Catálogo Do Acervo" in collection_report
        assert "Índice Mestre Da Pasta" in collection_report
