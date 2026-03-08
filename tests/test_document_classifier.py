from __future__ import annotations

import pytest

from index_all.indexing.document_classifier import classify_document_archetype


@pytest.mark.parametrize(
    ("metadata", "blocks", "parser_metadata", "expected"),
    (
        (
            {"file_name": "lei_complementar.docx", "file_stem": "lei_complementar", "file_type": "docx", "source_path": "lei_complementar.docx"},
            [{"kind": "article", "title": "Art. 1º", "text": "Esta lei estabelece normas gerais."}],
            {"mode": "structured_legal"},
            "legislation_normative",
        ),
        (
            {"file_name": "lei_alteradora.docx", "file_stem": "lei_alteradora", "file_type": "docx", "source_path": "lei_alteradora.docx"},
            [{"kind": "article", "title": "Art. 1º", "text": "Esta lei altera a Lei Complementar nº 123 e dá nova redação ao art. 2º."}],
            {"mode": "structured_legal"},
            "legislation_amending_act",
        ),
        (
            {"file_name": "manual_operacional.pdf", "file_stem": "manual_operacional", "file_type": "pdf", "source_path": "manual_operacional.pdf"},
            [{"kind": "heading", "title": "Manual de Procedimentos", "text": "Passo a passo para execução da rotina."}],
            {"mode": "page_text"},
            "manual_procedural",
        ),
        (
            {"file_name": "acordao.pdf", "file_stem": "acordao", "file_type": "pdf", "source_path": "acordao.pdf"},
            [{"kind": "page_text", "title": "Acórdão", "text": "ACÓRDÃO. Processo n. 5001234-56.2024.8.26.0000. Relator: Fulano."}],
            {"mode": "page_text"},
            "judicial_case",
        ),
        (
            {"file_name": "balancete.csv", "file_stem": "balancete", "file_type": "csv", "source_path": "balancete.csv"},
            [{"kind": "table_header", "title": "Header", "text": "Conta | Valor"}],
            {"mode": "table_preview"},
            "spreadsheet_structured",
        ),
        (
            {"file_name": "nfe.xml", "file_stem": "nfe", "file_type": "xml", "source_path": "nfe.xml"},
            [{"kind": "xml_node", "title": "infNFe", "text": "3514..."}],
            {"mode": "xml_tree", "root_tag": "nfeProc"},
            "xml_structured",
        ),
        (
            {"file_name": "extrato.ofx", "file_stem": "extrato", "file_type": "ofx", "source_path": "extrato.ofx"},
            [{"kind": "transaction", "title": None, "text": "2026-01-10 | DEBIT | -10.00 | TAXA"}],
            {"transaction_count": 1},
            "financial_statement_ofx",
        ),
        (
            {"file_name": "nota.txt", "file_stem": "nota", "file_type": "txt", "source_path": "nota.txt"},
            [{"kind": "paragraph", "title": "Observação", "text": "Texto livre sem sinais estruturais específicos."}],
            {"mode": "line_text"},
            "generic_document",
        ),
    ),
)
def test_classify_document_archetype_returns_expected_type(
    metadata: dict,
    blocks: list[dict],
    parser_metadata: dict,
    expected: str,
):
    assert classify_document_archetype(metadata, blocks, parser_metadata) == expected
