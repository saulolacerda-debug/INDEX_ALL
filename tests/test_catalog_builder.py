from __future__ import annotations

from pathlib import Path

from index_all.indexing.catalog_builder import build_catalog
from index_all.indexing.collection_summary_builder import build_collection_metadata, build_collection_summary
from index_all.indexing.master_index_builder import build_master_index


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
                {"id": "idx_0001", "title": "Preâmbulo", "kind": "preamble", "level": 1, "parent_id": None, "children": []},
                {"id": "idx_0002", "title": "Art. 1º", "kind": "article", "level": 8, "parent_id": None, "children": []},
            ],
            "output_dir": str(Path("saida") / "norma"),
        },
        {
            "metadata": {"file_name": "manual.pdf", "file_type": "pdf", "document_archetype": "manual_procedural"},
            "content": {
                "document_archetype": "manual_procedural",
                "blocks": [{"id": "block_0001"}],
                "document_profile": {"block_count": 1, "index_entry_count": 1},
            },
            "index": [
                {"id": "idx_0001", "title": "MANUAL OPERACIONAL", "kind": "heading", "level": 1, "parent_id": None, "children": []},
            ],
            "output_dir": str(Path("saida") / "manual"),
        },
    ]


def test_build_catalog_lists_expected_fields():
    catalog = build_catalog(_sample_processed_documents())

    assert len(catalog) == 2
    assert catalog[0]["file_name"] == "norma.docx"
    assert catalog[0]["file_type"] == "docx"
    assert catalog[0]["document_archetype"] == "legislation_normative"
    assert catalog[0]["block_count"] == 2
    assert catalog[0]["top_index_titles"] == ["Preâmbulo", "Art. 1º"]
    assert catalog[1]["document_archetype"] == "manual_procedural"
    assert catalog[1]["output_dir"].endswith("manual")


def test_collection_summary_builder_aggregates_collection_view():
    processed_documents = _sample_processed_documents()
    catalog = build_catalog(processed_documents)
    master_index = build_master_index(processed_documents)
    metadata = build_collection_metadata(Path("acervo"), catalog, master_index)
    summary = build_collection_summary(metadata, catalog, master_index)

    assert metadata["collection_name"] == "acervo"
    assert metadata["file_count"] == 2
    assert metadata["file_type_counts"] == {"docx": 1, "pdf": 1}
    assert metadata["document_archetype_counts"] == {
        "legislation_normative": 1,
        "manual_procedural": 1,
    }
    assert metadata["files_with_normative_structure"] == ["norma.docx"]
    assert metadata["files_with_procedural_structure"] == ["manual.pdf"]
    assert "Arquivos por tipo: docx: 1, pdf: 1." in summary
    assert "Arquivos com estrutura normativa: norma.docx." in summary
    assert "Arquivos com estrutura procedural: manual.pdf." in summary
