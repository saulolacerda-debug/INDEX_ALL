from __future__ import annotations

import json

from index_all.indexing.structure_indexer import build_structure_index
from index_all.main import iter_supported_files, process_file
from index_all.parsers.docx_parser import parse_docx

from tests.helpers import create_amending_docx, create_legal_docx, create_manual_docx, workspace_test_dir


def test_build_structure_index_creates_full_legal_hierarchy():
    with workspace_test_dir() as temp_dir:
        docx_path = create_legal_docx(temp_dir / "norma.docx")
        blocks = parse_docx(docx_path)["content"]["blocks"]

        index_entries = build_structure_index(blocks, document_archetype="legislation_normative")

        assert [entry["title"] for entry in index_entries[:2]] == ["Preâmbulo", "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES"]

        part_entry = index_entries[1]
        book_entry = part_entry["children"][0]
        title_entry = book_entry["children"][0]
        chapter_entry = title_entry["children"][0]
        section_entry = chapter_entry["children"][0]
        subsection_entry = section_entry["children"][0]
        article_entry = subsection_entry["children"][0]
        legal_paragraph_entry = article_entry["children"][0]
        inciso_entry = legal_paragraph_entry["children"][0]
        alinea_entry = inciso_entry["children"][0]
        item_entry = alinea_entry["children"][0]

        assert book_entry["title"] == "Livro I - DISPOSIÇÕES GERAIS"
        assert title_entry["title"] == "Título I - DAS NORMAS INICIAIS"
        assert chapter_entry["title"] == "Capítulo I - DA ORGANIZAÇÃO"
        assert section_entry["title"] == "Seção I - Das Regras Básicas"
        assert subsection_entry["title"] == "Subseção I - Da Estrutura Inicial"
        assert article_entry["title"] == "Art. 1º - Esta lei estabelece normas gerais"
        assert legal_paragraph_entry["title"] == "§ 1º"
        assert inciso_entry["title"] == "Inciso I"
        assert alinea_entry["title"] == "Alínea a"
        assert item_entry["title"] == "Item 1"
        assert subsection_entry["children"][1]["title"] == "Art. 2º - Ficam revogadas as disposições em contrário"


def test_build_structure_index_keeps_flat_fallback():
    blocks = [
        {
            "kind": "paragraph",
            "title": "Item 1",
            "text": "Conteúdo 1",
            "locator": {"page": 1},
            "extra": {},
        }
    ]

    result = build_structure_index(blocks, document_archetype="generic_document")

    assert len(result) == 1
    assert result[0]["title"] == "Item 1"
    assert result[0]["children"] == []


def test_build_structure_index_nests_amended_devices_under_act_article():
    with workspace_test_dir() as temp_dir:
        docx_path = create_amending_docx(temp_dir / "ec_132.docx")
        blocks = parse_docx(docx_path)["content"]["blocks"]

        index_entries = build_structure_index(blocks, document_archetype="legislation_amending_act")

        article_1_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 1º"))
        article_2_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 2º"))

        amended_children = [child for child in article_1_entry["children"] if child["kind"] == "article"]
        assert [child["title"] for child in amended_children] == [
            "Art. 43 - Compete à lei complementar disciplinar aspectos gerais do sistema",
            "Art. 50 - O Congresso Nacional e suas Casas terão competência para fiscalizar a execução",
            "Art. 105 - Compete ao Superior Tribunal de Justiça",
        ]
        assert article_2_entry["title"] == "Art. 2º - Esta Emenda Constitucional entra em vigor na data de sua publicação"
        assert all(not entry["title"].startswith("Art. 43") for entry in index_entries)
        assert amended_children[0]["children"][0]["title"] == "§ 4º"
        assert amended_children[2]["children"][0]["title"] == "Inciso I"
        assert amended_children[2]["children"][0]["children"][0]["title"] == "Alínea j"


def test_pipeline_ignores_helper_files_and_writes_hierarchical_summary():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        (source_dir / ".gitkeep").write_text("", encoding="utf-8")
        (source_dir / "Thumbs.db").write_text("", encoding="utf-8")

        files = iter_supported_files(source_dir)

        assert [path.name for path in files] == ["norma.docx"]

        output_dir = process_file(files[0], temp_root / "saida")

        ai_context_payload = json.loads((output_dir / "ai_context.json").read_text(encoding="utf-8"))
        ai_context_markdown = (output_dir / "ai_context.md").read_text(encoding="utf-8")
        metadata_payload = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
        content_payload = json.loads((output_dir / "content.json").read_text(encoding="utf-8"))
        index_entries = json.loads((output_dir / "index.json").read_text(encoding="utf-8"))
        summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
        report_html = (output_dir / "report.html").read_text(encoding="utf-8")

        assert metadata_payload["file_name"] == "norma.docx"
        assert metadata_payload["artifact_role"] == "document_manifest"
        assert metadata_payload["document_archetype"] == "legislation_normative"
        assert metadata_payload["document_profile"]["domain"] == "legal_normative"
        assert metadata_payload["document_profile"]["document_archetype"] == "legislation_normative"
        assert metadata_payload["consultation_hints"]["preferred_artifact_for_grounding"] == "ai_context.json"
        assert metadata_payload["consultation_hints"]["preferred_markdown_artifact_for_upload"] == "ai_context.md"
        assert metadata_payload["consultation_hints"]["compact_grounding_artifact"] == "content.json"
        assert metadata_payload["available_artifacts"]["ai_context"] == "ai_context.json"
        assert metadata_payload["available_artifacts"]["ai_context_markdown"] == "ai_context.md"
        assert metadata_payload["available_artifacts"]["index"] == "index.json"
        assert metadata_payload["ai_ready"]["single_file_ready"] is False
        assert metadata_payload["ai_ready"]["preferred_artifact_for_upload"] == "ai_context.json"
        assert metadata_payload["ai_ready"]["preferred_markdown_artifact_for_upload"] == "ai_context.md"

        assert content_payload["metadata"]["file_name"] == "norma.docx"
        assert content_payload["document_archetype"] == "legislation_normative"
        assert content_payload["document_profile"]["domain"] == "legal_normative"
        assert content_payload["document_profile"]["document_archetype"] == "legislation_normative"
        assert content_payload["document_profile"]["primary_structure"] == "structured_legal"
        assert content_payload["ai_ready"]["single_file_ready"] is True
        assert content_payload["ai_ready"]["preferred_upload_unit"] is False
        assert content_payload["ai_ready"]["preferred_artifact_for_upload"] == "ai_context.json"
        assert content_payload["ai_ready"]["preferred_markdown_artifact_for_upload"] == "ai_context.md"
        assert content_payload["summary"]
        assert content_payload["index"][1]["title"] == "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES"
        assert content_payload["blocks"][0]["source_reference"]
        assert content_payload["blocks"][0]["text_preview"]
        assert content_payload["blocks"][7]["display_title"] == "Art. 1º - Esta lei estabelece normas gerais"

        assert ai_context_payload["artifact_role"] == "ai_context_bundle"
        assert ai_context_payload["schema_version"] == "1.0"
        assert ai_context_payload["document_archetype"] == "legislation_normative"
        assert ai_context_payload["document_profile"]["domain"] == "legal_normative"
        assert ai_context_payload["document_profile"]["document_archetype"] == "legislation_normative"
        assert ai_context_payload["metadata"]["artifact_role"] == "document_manifest"
        assert ai_context_payload["consultation_hints"]["preferred_artifact_for_grounding"] == "ai_context.json"
        assert ai_context_payload["ai_ready"]["single_file_ready"] is True
        assert ai_context_payload["ai_ready"]["preferred_upload_unit"] is True
        assert ai_context_payload["ai_ready"]["preferred_markdown_artifact_for_upload"] == "ai_context.md"
        assert ai_context_payload["index"][1]["descendant_count"] > 0
        assert ai_context_payload["blocks"][7]["source_reference"]

        assert index_entries[0]["title"] == "Preâmbulo"
        assert index_entries[0]["document_context"]["domain"] == "legal_normative"
        assert index_entries[0]["document_context"]["document_archetype"] == "legislation_normative"
        assert index_entries[0]["source_reference"]
        assert index_entries[0]["position_text"]
        assert index_entries[1]["descendant_count"] > 0
        assert index_entries[1]["children"][0]["children"][0]["children"][0]["children"][0]["locator_path"] == "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES > Livro I - DISPOSIÇÕES GERAIS > Título I - DAS NORMAS INICIAIS > Capítulo I - DA ORGANIZAÇÃO > Seção I - Das Regras Básicas"
        assert index_entries[1]["title"] == "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES"
        assert index_entries[1]["children"][0]["children"][0]["children"][0]["children"][0]["title"] == "Seção I - Das Regras Básicas"
        assert "## Como Usar Com IA" in summary_text
        assert "## Perfil Do Documento" in summary_text
        assert "- Arquétipo documental: `legislation_normative`" in summary_text
        assert "## Índice Hierárquico Completo" in summary_text
        assert "## Blocos Estruturados" in summary_text
        assert "ai_context.json" in summary_text
        assert "ai_context.md" in summary_text
        assert "Referência de citação" in summary_text
        assert "[block_0008] Art. 1º - Esta lei estabelece normas gerais" in summary_text
        assert "```text" in summary_text
        assert "- [preamble] Preâmbulo" in summary_text
        assert "- [part] Parte Geral - DAS DISPOSIÇÕES PRELIMINARES" in summary_text
        assert "  - [book] Livro I - DISPOSIÇÕES GERAIS" in summary_text
        assert "            - [article] Art. 1º - Esta lei estabelece normas gerais" in summary_text
        assert "Estrutura identificada:" in summary_text
        assert "subseção(ões)" in summary_text
        assert "item(ns)" in summary_text
        assert "INDEX_ALL Report" in report_html
        assert "Relatório navegável" in report_html
        assert "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES" in report_html
        assert "Art. 1º - Esta lei estabelece normas gerais" in report_html
        assert "Art. 1º Esta lei estabelece normas gerais." in report_html
        assert "Visão Geral" not in report_html
        assert "report-data" in report_html
        assert "content-scroll" in report_html
        assert "Copiar referência" in report_html
        assert "search-hit" in report_html
        assert "nodeContainsSelected" in report_html
        assert "navigator.clipboard" in report_html
        assert "selected-breadcrumb" in report_html
        assert "Copiar link estrutural" in report_html
        assert "Exportar trecho" in report_html
        assert "resolveHashTarget" in report_html
        assert "#ref=" in report_html
        assert "buildStructuralLink" in report_html
        assert "overflow-x: auto" in report_html
        assert "210mm" in report_html
        assert "#07306C" in report_html
        assert "#046B91" in report_html
        assert "#075EAD" in report_html
        assert "#499A9E" in report_html
        assert "#DF9E51" in report_html
        assert "#0F172A" in report_html
        assert "#CBD5E1" in report_html

        assert "# AI Context - norma.docx" in ai_context_markdown
        assert "- Arquétipo documental: `legislation_normative`" in ai_context_markdown
        assert "upload em IA quando o modelo responder melhor a Markdown" in ai_context_markdown
        assert "- Artefato preferencial para upload textual: `ai_context.md`" in ai_context_markdown
        assert "- Artefato preferencial para upload JSON: `ai_context.json`" in ai_context_markdown
        assert "## Entradas De Alto Nível" in ai_context_markdown
        assert "## Índice Hierárquico Completo" in ai_context_markdown
        assert "## Blocos Estruturados" in ai_context_markdown
        assert "[block_0008] Art. 1º - Esta lei estabelece normas gerais" in ai_context_markdown


def test_pipeline_writes_manual_procedural_tree_without_page_backbone():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_manual_docx(source_dir / "manual_operacional.docx")

        output_dir = process_file(source_dir / "manual_operacional.docx", temp_root / "saida")

        content_payload = json.loads((output_dir / "content.json").read_text(encoding="utf-8"))
        summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
        report_html = (output_dir / "report.html").read_text(encoding="utf-8")

        assert content_payload["document_archetype"] == "manual_procedural"
        assert content_payload["document_profile"]["primary_structure"] == "structured_manual"
        assert content_payload["index"][0]["title"] == "MANUAL OPERACIONAL DE APURAÇÃO"
        assert content_payload["index"][0]["children"][0]["title"] == "Primeiros Passos"
        assert content_payload["index"][0]["children"][0]["children"][0]["title"] == "Objetivos"
        assert content_payload["index"][0]["children"][0]["children"][1]["title"] == "Procedimento"
        assert content_payload["index"][0]["children"][0]["children"][1]["children"][0]["title"] == "Etapa 1 - Receber arquivo"
        assert "- [heading] MANUAL OPERACIONAL DE APURAÇÃO" in summary_text
        assert "- [heading] Primeiros Passos" in summary_text
        assert "Page 1" not in summary_text
        assert "Page 1" not in report_html
        assert "índice procedural por títulos, seções e etapas internas" in report_html
