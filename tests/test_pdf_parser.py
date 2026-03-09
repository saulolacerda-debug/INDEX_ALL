from __future__ import annotations

from index_all.indexing.structure_indexer import build_structure_index
from index_all.parsers.pdf_parser import build_blocks_from_page_texts, parse_pdf

from tests.helpers import AMENDING_SCOPE_SAMPLE_LINES, NORMATIVE_WITH_FINAL_AMENDMENTS_LINES


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


def test_pdf_parser_closes_embedded_scope_when_main_amending_article_resumes():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(AMENDING_SCOPE_SAMPLE_LINES[:8]),
            "\n".join(AMENDING_SCOPE_SAMPLE_LINES[8:]),
        ]
    )

    index_entries = build_structure_index(blocks, document_archetype="legislation_amending_act")
    article_1_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 1º"))
    article_2_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 2º"))
    article_3_entry = next(entry for entry in index_entries if entry["kind"] == "article" and entry["title"].startswith("Art. 3º"))
    embedded_section = next(child for child in article_1_entry["children"] if child["kind"] == "section")

    assert mode == "structured_legal"
    assert embedded_section["title"] == "Seção V-A - Do Comitê Gestor do Imposto sobre Bens e Serviços"
    assert any(child["title"].startswith("Art. 43") for child in embedded_section["children"])
    assert article_2_entry["parent_id"] is None
    assert article_3_entry["parent_id"] is None
    assert all(not child["title"].startswith("Art. 2º") for child in article_1_entry["children"])
    assert all(not child["title"].startswith("Art. 3º") for child in article_1_entry["children"])


def test_pdf_parser_does_not_promote_cross_references_to_fake_articles():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(
                (
                    "LEI COMPLEMENTAR Nº 227, DE 13 DE JANEIRO DE 2026",
                    "O PRESIDENTE DA REPÚBLICA Faço saber que o Congresso Nacional decreta e eu sanciono a seguinte Lei Complementar:",
                    "Art. 1º Esta Lei Complementar institui normas gerais do IBS e da CBS.",
                    "Art. 108 desta Lei Complementar aplica-se às operações de importação.",
                    "Art. 136 do ADCT permanece aplicável às hipóteses de transição.",
                    "Art. 2º O regime específico aplica-se às hipóteses previstas nesta Lei Complementar.",
                )
            )
        ]
    )

    article_titles = [block["title"] for block in blocks if block["kind"] == "article"]

    assert mode == "structured_legal"
    assert article_titles == ["Art. 1º", "Art. 2º"]


def test_pdf_parser_builds_manual_without_duplicate_toc_and_with_valid_locators():
    blocks, mode = build_blocks_from_page_texts(
        [
            "\n".join(
                (
                    "APURAÇÃO ASSISTIDA - PRIMEIROS PASSOS",
                    "1. Objetivos",
                    "2. Procedimento",
                    "3. Resumo",
                )
            ),
            "\n".join(
                (
                    "1. Objetivos",
                    "Apresentar o fluxo inicial de conferência.",
                    "2. Procedimento",
                    "Etapa 1 - Acessar portal",
                    "Portal TRIBUTOS SOBRE BENS E SERVIÇOS",
                    "Clique no botão Enviar",
                    "3. Resumo",
                    "Registrar o resultado final no sistema.",
                )
            ),
        ]
    )

    index_entries = build_structure_index(blocks, document_archetype="manual_procedural")
    top_entry = index_entries[0]
    child_titles = [child["title"] for child in top_entry["children"]]
    step_entry = top_entry["children"][1]["children"][0]
    interface_blocks = [block for block in blocks if (block.get("extra", {}) or {}).get("manual_group") == "interface_label"]

    assert mode == "structured_manual"
    assert top_entry["title"] == "APURAÇÃO ASSISTIDA - PRIMEIROS PASSOS"
    assert child_titles == ["1. Objetivos", "2. Procedimento", "3. Resumo"]
    assert step_entry["title"] == "Etapa 1 - Acessar portal"
    assert not step_entry["children"]
    assert [block["text"] for block in interface_blocks] == ["Portal TRIBUTOS SOBRE BENS E SERVIÇOS"]
    assert all(entry["title"] != "Page 1" for entry in index_entries)
    assert all(
        locator.get("line_start") is None
        or locator.get("line_end") is None
        or locator["line_start"] <= locator["line_end"]
        for locator in (block["locator"] for block in blocks)
    )


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
