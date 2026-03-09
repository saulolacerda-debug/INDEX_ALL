from __future__ import annotations

from index_all.main import process_file
from index_all.semantics.chunker import build_document_chunks
from index_all.semantics.search_engine import load_processed_document

from tests.helpers import create_amending_docx, create_legal_docx, create_manual_docx, workspace_test_dir


def test_chunker_builds_normative_chunks_by_article_with_locator_and_heading_path():
    with workspace_test_dir() as temp_root:
        docx_path = create_legal_docx(temp_root / "norma.docx")
        output_dir = process_file(docx_path, temp_root / "saida")
        processed_document = load_processed_document(output_dir)

        chunks = build_document_chunks(processed_document)

        assert chunks
        first_chunk = chunks[0]
        assert first_chunk["document_archetype"] == "legislation_normative"
        assert first_chunk["heading"].startswith("Art. 1º")
        assert first_chunk["heading_path"][-1].startswith("Art. 1º")
        assert first_chunk["locator"]["article"] == "Art. 1º"
        assert "Esta lei estabelece normas gerais" in first_chunk["text"]


def test_chunker_builds_amending_chunks_with_act_article_context():
    with workspace_test_dir() as temp_root:
        docx_path = create_amending_docx(temp_root / "ec_132.docx")
        output_dir = process_file(docx_path, temp_root / "saida")
        processed_document = load_processed_document(output_dir)

        chunks = build_document_chunks(processed_document)
        amended_chunk = next(chunk for chunk in chunks if chunk["heading"].startswith("Art. 43"))

        assert amended_chunk["document_archetype"] == "legislation_amending_act"
        assert amended_chunk["metadata"]["root_context"]["act_article_title"].startswith("Art. 1º")
        assert any(path.startswith("Art. 1º") for path in amended_chunk["heading_path"])
        assert amended_chunk["heading_path"][-1].startswith("Art. 43")


def test_chunker_builds_manual_chunks_by_section_or_step():
    with workspace_test_dir() as temp_root:
        docx_path = create_manual_docx(temp_root / "manual.docx")
        output_dir = process_file(docx_path, temp_root / "saida")
        processed_document = load_processed_document(output_dir)

        chunks = build_document_chunks(processed_document)
        headings = [chunk["heading"] for chunk in chunks]

        assert any(heading == "Objetivos" for heading in headings)
        assert any(heading.startswith("Etapa 1") for heading in headings)
        objetivos_chunk = next(chunk for chunk in chunks if chunk["heading"] == "Objetivos")
        assert objetivos_chunk["document_archetype"] == "manual_procedural"
        assert objetivos_chunk["locator"]["line_start"] is not None
        assert objetivos_chunk["heading_path"][-1] == "Objetivos"
