from __future__ import annotations

from index_all.parsers.docx_parser import parse_docx

from tests.helpers import create_legal_docx, workspace_test_dir


def test_docx_parser_classifies_full_legal_structure():
    with workspace_test_dir() as temp_dir:
        docx_path = create_legal_docx(temp_dir / "norma.docx")

        result = parse_docx(docx_path)
        blocks = result["content"]["blocks"]
        preamble_block = next(block for block in blocks if block["kind"] == "preamble")
        assert preamble_block["kind"] == "preamble"
        assert preamble_block["title"] == "Preâmbulo"
        assert "LEI COMPLEMENTAR Nº 999" in preamble_block["text"]

        part_block = next(block for block in blocks if block["kind"] == "part")
        book_block = next(block for block in blocks if block["kind"] == "book")
        title_block = next(block for block in blocks if block["kind"] == "title")
        chapter_block = next(block for block in blocks if block["kind"] == "chapter")
        section_block = next(block for block in blocks if block["kind"] == "section")
        subsection_block = next(block for block in blocks if block["kind"] == "subsection")

        assert part_block["title"] == "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES"
        assert book_block["title"] == "Livro I - DISPOSIÇÕES GERAIS"
        assert title_block["title"] == "Título I - DAS NORMAS INICIAIS"
        assert chapter_block["title"] == "Capítulo I - DA ORGANIZAÇÃO"
        assert section_block["title"] == "Seção I - Das Regras Básicas"
        assert subsection_block["title"] == "Subseção I - Da Estrutura Inicial"

        article_block = next(block for block in blocks if block["title"] == "Art. 1º")
        assert article_block["kind"] == "article"
        assert article_block["title"] == "Art. 1º"
        assert article_block["extra"]["display_title"] == "Art. 1º - Esta lei estabelece normas gerais"
        assert article_block["extra"]["summary"] == "Esta lei estabelece normas gerais"
        assert article_block["locator"]["section"] == "Seção I - Das Regras Básicas"
        assert article_block["locator"]["subsection"] == "Subseção I - Da Estrutura Inicial"

        legal_paragraph_block = next(block for block in blocks if block["title"] == "§ 1º")
        assert legal_paragraph_block["kind"] == "legal_paragraph"
        assert legal_paragraph_block["title"] == "§ 1º"
        assert legal_paragraph_block["locator"]["article"] == "Art. 1º"

        inciso_block = next(block for block in blocks if block["title"] == "Inciso I")
        assert inciso_block["kind"] == "inciso"
        assert inciso_block["title"] == "Inciso I"
        assert inciso_block["locator"]["paragraph"] == "§ 1º"

        alinea_block = next(block for block in blocks if block["title"] == "Alínea a")
        assert alinea_block["kind"] == "alinea"
        assert alinea_block["title"] == "Alínea a"
        assert alinea_block["locator"]["inciso"] == "Inciso I"

        item_block = next(block for block in blocks if block["title"] == "Item 1")
        assert item_block["kind"] == "item"
        assert item_block["title"] == "Item 1"
        assert item_block["locator"]["alinea"] == "Alínea a"

        parser_metadata = result["content"]["parser_metadata"]
        assert parser_metadata["kind_counts"]["preamble"] == 1
        assert parser_metadata["kind_counts"]["part"] == 1
        assert parser_metadata["kind_counts"]["subsection"] == 1
        assert parser_metadata["kind_counts"]["item"] == 1
