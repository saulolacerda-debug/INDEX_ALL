from __future__ import annotations

from index_all.parsers.pdf_parser import build_blocks_from_page_texts, parse_pdf


def test_pdf_parser_builds_full_legal_structure_from_page_text():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(
                (
                    "LEI COMPLEMENTAR Nº 227, DE 13 DE JANEIRO DE 2026",
                    "O PRESIDENTE DA REPÚBLICA Faço saber que o Congresso Nacional decreta e eu sanciono a seguinte Lei Complementar:",
                    "PARTE GERAL",
                    "DAS DISPOSIÇÕES PRELIMINARES",
                    "LIVRO I",
                    "DISPOSIÇÕES GERAIS",
                    "TÍTULO I",
                    "DAS NORMAS INICIAIS",
                    "CAPÍTULO I",
                    "DA ORGANIZAÇÃO",
                    "Seção I",
                    "Das Regras Básicas",
                    "Subseção I",
                    "Da Estrutura Inicial",
                    "Art. 1º Esta lei estabelece normas gerais.",
                    "Parágrafo único. O CGIBS observará a coordenação nacional.",
                    "I - observar a legalidade;",
                )
            ),
            "\n".join(
                (
                    "a) cumprir requisitos mínimos;",
                    "1. registrar atos essenciais;",
                    "Art. 2º Ficam revogadas as disposições em contrário.",
                )
            ),
        ]
    )

    assert mode == "structured_legal"
    assert [block["kind"] for block in blocks[:10]] == [
        "preamble",
        "part",
        "book",
        "title",
        "chapter",
        "section",
        "subsection",
        "article",
        "legal_paragraph",
        "inciso",
    ]

    preamble_block = blocks[0]
    part_block = blocks[1]
    subsection_block = blocks[6]
    article_block = blocks[7]
    unique_paragraph_block = blocks[8]
    inciso_block = blocks[9]
    alinea_block = blocks[10]
    item_block = blocks[11]
    second_article_block = blocks[12]

    assert preamble_block["title"] == "Preâmbulo"
    assert part_block["title"] == "Parte Geral - DAS DISPOSIÇÕES PRELIMINARES"
    assert subsection_block["title"] == "Subseção I - Da Estrutura Inicial"
    assert article_block["title"] == "Art. 1º"
    assert article_block["extra"]["display_title"] == "Art. 1º - Esta lei estabelece normas gerais"
    assert unique_paragraph_block["title"] == "Parágrafo único"
    assert unique_paragraph_block["locator"]["article"] == "Art. 1º"
    assert inciso_block["title"] == "Inciso I"
    assert inciso_block["locator"]["paragraph"] == "Parágrafo único"
    assert alinea_block["title"] == "Alínea a"
    assert alinea_block["locator"]["inciso"] == "Inciso I"
    assert item_block["title"] == "Item 1"
    assert item_block["locator"]["alinea"] == "Alínea a"
    assert item_block["locator"]["page"] == 2
    assert second_article_block["title"] == "Art. 2º"
    assert second_article_block["extra"]["display_title"] == "Art. 2º - Ficam revogadas as disposições em contrário"


def test_pdf_parser_keeps_page_fallback_for_non_legal_text():
    blocks, mode = build_blocks_from_page_texts(
        [
            "APURAÇÃO ASSISTIDA\nPRIMEIROS PASSOS\nOBJETIVOS:\n1. Simular uma venda.",
            "PASSOS:\n1º) Enviar XML.\n2º) Verificar a apuração.",
        ]
    )

    assert mode == "page_text"
    assert len(blocks) == 2
    assert blocks[0]["kind"] == "page_text"
    assert blocks[0]["title"] == "Page 1"
    assert blocks[1]["locator"]["page"] == 2


def test_pdf_parser_importable():
    assert callable(parse_pdf)
