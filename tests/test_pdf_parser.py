from __future__ import annotations

from index_all.indexing.structure_indexer import build_structure_index
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


def test_pdf_parser_builds_structured_manual_instead_of_page_backbone():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(
                (
                    "MANUAL OPERACIONAL DE APURAÇÃO",
                    "PRIMEIROS PASSOS",
                    "OBJETIVOS:",
                    "Apresentar o fluxo inicial de conferência.",
                    "PROCEDIMENTO:",
                    "Etapa 1 - Receber arquivo",
                    "Verificar extensão e integridade.",
                )
            ),
            "\n".join(
                (
                    "Etapa 2 - Validar conteúdo",
                    "Conferir campos obrigatórios.",
                    "RESUMO",
                    "Registrar o resultado final no sistema.",
                )
            ),
        ]
    )

    index_entries = build_structure_index(blocks, document_archetype="manual_procedural")

    assert mode == "structured_manual"
    assert all(block["kind"] != "page_text" for block in blocks)
    assert blocks[0]["title"] == "MANUAL OPERACIONAL DE APURAÇÃO"
    assert index_entries[0]["title"] == "MANUAL OPERACIONAL DE APURAÇÃO"
    assert index_entries[0]["children"][0]["title"] == "PRIMEIROS PASSOS"
    assert index_entries[0]["children"][0]["children"][0]["title"] == "OBJETIVOS"
    assert index_entries[0]["children"][0]["children"][1]["title"] == "PROCEDIMENTO"
    assert index_entries[0]["children"][0]["children"][1]["children"][0]["title"] == "Etapa 1 - Receber arquivo"


def test_pdf_parser_keeps_amended_devices_nested_under_amending_article():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(
                (
                    "EMENDA CONSTITUCIONAL Nº 132, DE 20 DE DEZEMBRO DE 2023",
                    "As Mesas da Câmara dos Deputados e do Senado Federal promulgam a seguinte Emenda ao texto constitucional:",
                    "Art. 1º Os arts. 43, 50 e 105 da Constituição Federal passam a vigorar com as seguintes alterações:",
                    "Art. 43. Compete à lei complementar disciplinar aspectos gerais do sistema.",
                    "§ 4º Lei complementar poderá estabelecer normas específicas de coordenação.",
                    "Art. 50. O Congresso Nacional e suas Casas terão competência para fiscalizar a execução.",
                )
            ),
            "\n".join(
                (
                    "Art. 105. Compete ao Superior Tribunal de Justiça:",
                    "I - processar e julgar, originariamente, os conflitos de competência;",
                    "j) conflitos entre autoridades administrativas e judiciais relacionados ao novo regime;",
                    "Art. 2º Esta Emenda Constitucional entra em vigor na data de sua publicação.",
                )
            ),
        ]
    )

    index_entries = build_structure_index(blocks, document_archetype="legislation_amending_act")
    article_1_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 1º"))
    amended_children = [child for child in article_1_entry["children"] if child["kind"] == "article"]

    assert mode == "structured_legal"
    assert [child["title"] for child in amended_children] == [
        "Art. 43 - Compete à lei complementar disciplinar aspectos gerais do sistema",
        "Art. 50 - O Congresso Nacional e suas Casas terão competência para fiscalizar a execução",
        "Art. 105 - Compete ao Superior Tribunal de Justiça",
    ]
    assert amended_children[0]["children"][0]["title"] == "§ 4º"
    assert amended_children[2]["children"][0]["title"] == "Inciso I"
    assert amended_children[2]["children"][0]["children"][0]["title"] == "Alínea j"


def test_pdf_parser_keeps_page_fallback_for_generic_non_structured_text():
    blocks, mode = build_blocks_from_page_texts(
        [
            "Registro de ocorrências do plantão.\nTexto corrido sem estrutura interna confiável.",
            "Continuação narrativa com observações livres e sem seções detectáveis.",
        ]
    )

    assert mode == "page_text"
    assert len(blocks) == 2
    assert blocks[0]["kind"] == "page_text"
    assert blocks[0]["title"] == "Page 1"
    assert blocks[1]["locator"]["page"] == 2


def test_pdf_parser_importable():
    assert callable(parse_pdf)
