from __future__ import annotations

from pathlib import Path
from typing import Callable

from index_all.parsers.csv_parser import parse_csv
from index_all.parsers.docx_parser import parse_docx
from index_all.parsers.html_parser import parse_html
from index_all.parsers.ofx_parser import parse_ofx
from index_all.parsers.pdf_parser import parse_pdf
from index_all.parsers.txt_parser import parse_txt
from index_all.parsers.xlsx_parser import parse_xlsx
from index_all.parsers.xml_parser import parse_xml


ParserFunc = Callable[[Path], dict]
IGNORED_FILE_NAMES = {".gitkeep", ".ds_store", "thumbs.db"}

PARSER_MAP: dict[str, ParserFunc] = {
    ".csv": parse_csv,
    ".docx": parse_docx,
    ".htm": parse_html,
    ".html": parse_html,
    ".ofx": parse_ofx,
    ".pdf": parse_pdf,
    ".txt": parse_txt,
    ".xlsx": parse_xlsx,
    ".xml": parse_xml,
}


class IgnoredPathError(ValueError):
    pass


def is_ignored_path(path: Path) -> bool:
    return path.name.casefold() in IGNORED_FILE_NAMES


def get_parser_for_path(path: Path) -> ParserFunc:
    if is_ignored_path(path):
        raise IgnoredPathError(f"Ignored helper file: {path.name}")
    suffix = path.suffix.lower()
    if suffix not in PARSER_MAP:
        raise ValueError(f"Unsupported file type: {suffix}")
    return PARSER_MAP[suffix]
