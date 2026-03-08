from __future__ import annotations

import pytest

from index_all.indexing.structure_indexer import build_structure_index
from index_all.parsers.csv_parser import parse_csv
from index_all.parsers.html_parser import parse_html
from index_all.parsers.txt_parser import parse_txt
from index_all.parsers.xlsx_parser import parse_xlsx
from index_all.parsers.xml_parser import parse_xml

from tests.helpers import (
    create_legal_csv,
    create_legal_html,
    create_legal_txt,
    create_legal_xlsx,
    create_legal_xml,
    workspace_test_dir,
)


@pytest.mark.parametrize(
    ("creator", "parser", "file_name"),
    (
        (create_legal_html, parse_html, "norma.html"),
        (create_legal_xml, parse_xml, "norma.xml"),
        (create_legal_txt, parse_txt, "norma.txt"),
        (create_legal_csv, parse_csv, "norma.csv"),
        (create_legal_xlsx, parse_xlsx, "norma.xlsx"),
    ),
)
def test_textual_parsers_detect_legal_hierarchy_across_extensions(creator, parser, file_name):
    with workspace_test_dir() as temp_dir:
        file_path = creator(temp_dir / file_name)

        result = parser(file_path)
        blocks = result["content"]["blocks"]
        parser_metadata = result["content"]["parser_metadata"]
        index_entries = build_structure_index(blocks)

        assert parser_metadata["mode"] == "structured_legal"
        assert blocks[0]["kind"] == "preamble"
        assert any(block["kind"] == "part" for block in blocks)
        assert any(block["kind"] == "book" for block in blocks)
        assert any(block["kind"] == "subsection" for block in blocks)
        assert any(block["kind"] == "item" for block in blocks)

        item_block = next(block for block in blocks if block["kind"] == "item")
        assert item_block["title"] == "Item 1"
        assert item_block["locator"]["alinea"] == "Alínea a"

        part_entry = next(entry for entry in index_entries if entry["kind"] == "part")
        book_entry = part_entry["children"][0]
        title_entry = book_entry["children"][0]
        chapter_entry = title_entry["children"][0]
        section_entry = chapter_entry["children"][0]
        subsection_entry = section_entry["children"][0]
        article_entry = subsection_entry["children"][0]

        assert part_entry["title"].startswith("Parte Geral")
        assert book_entry["title"] == "Livro I - DISPOSIÇÕES GERAIS"
        assert subsection_entry["title"] == "Subseção I - Da Estrutura Inicial"
        assert article_entry["title"] == "Art. 1º - Esta lei estabelece normas gerais"
