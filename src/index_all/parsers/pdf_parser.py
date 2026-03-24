from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from index_all.parsers.legal_structure import (
    StructuredTextRecord,
    build_legal_blocks,
    build_manual_blocks,
    fold_text,
    looks_like_legal_document,
    looks_like_manual_document,
    make_preview_title,
    normalize_text,
)


PDF_HEADER_RE = re.compile(r"^\d+\s+N[úu]mero\s+\d+\s*[–-]\s*\d{2}/\d{2}/\d{4}$", re.IGNORECASE)
PDF_PAGE_ONLY_RE = re.compile(r"^\d+$")
PDF_PAGE_LABEL_RE = re.compile(r"^page\s+\d+$", re.IGNORECASE)
PDF_SEPARATOR_RE = re.compile(r"^[\._\-\s]{20,}$")
MANUAL_TITLE_HINTS = ("manual", "procedimento", "passo a passo", "guia")
MANUAL_STRUCTURE_HINTS = ("objetivos", "passos", "procedimento", "etapa", "etapas", "resumo")
MANUAL_OPERATION_HINTS = ("clique", "portal", "botão", "botao", "tela", "simulador")
PDF_EXACT_IGNORABLE_LINES = {
    "ocultar",
    "pagina inicial",
    "proximo resultado",
    "proximo resultadoocultar",
    "resultado anterior",
    "resultado anterior proximo resultado",
    "voltar para resultado da pesquisa",
}
PDF_INLINE_IGNORABLE_PATTERNS = (
    re.compile(r"\bP\S*gina Inicial\b", re.IGNORECASE),
    re.compile(r"\bResultado Anterior\b", re.IGNORECASE),
    re.compile(r"\bPr[oó]ximo Resultado(?:Ocultar)?\b", re.IGNORECASE),
    re.compile(r"\bVoltar para resultado da pesquisa\b", re.IGNORECASE),
    re.compile(r"\bOcultar\b", re.IGNORECASE),
)
FAQ_QUESTION_RE = re.compile(
    r"(?P<question>(?:Qual\b|Quais\b|Como\b|Quando\b|Onde\b|Quem\b|O\s+que\b|Por\s+que\b|Porque\b)[^?]{12,420}\?)",
    re.IGNORECASE,
)
FAQ_ARTICLE_START_RE = re.compile(r"\b(?:O|A|Os|As)\b")
PDF_LEADING_HOME_RE = re.compile(r"^[Pp].{0,12}?Inicial\s+", re.IGNORECASE)
PDF_EDOCS_PAGE_RE = re.compile(r"\bE-DOCS\s*-\s*DOCUMENTO ORIGINAL\b", re.IGNORECASE)
PDF_EDOCS_SIGNATURE_PAGE_HINT_RE = re.compile(
    r"documento original assinado eletronicamente|informações do documento|informacoes do documento",
    re.IGNORECASE,
)
PDF_IGNORABLE_LINE_PATTERNS = (
    re.compile(r"\bE-DOCS\s*-\s*DOCUMENTO ORIGINAL\b", re.IGNORECASE),
    re.compile(r"^Documento original assinado eletronicamente, conforme MP 2200-2/2001", re.IGNORECASE),
    re.compile(r"^assinado em \d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s+-\d{2}:\d{2}", re.IGNORECASE),
    re.compile(r"^Valor Legal:\s*ORIGINAL\b", re.IGNORECASE),
    re.compile(r"\bNatureza:\s*DOCUMENTO NATO-DIGITAL\b", re.IGNORECASE),
    re.compile(r"https://e-docs\.es\.gov\.br/", re.IGNORECASE),
    re.compile(r"^\(assinado digitalmente\)$", re.IGNORECASE),
)


def _strip_inline_pdf_boilerplate(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""

    for pattern in PDF_INLINE_IGNORABLE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)

    return normalize_text(cleaned)


def _strip_leading_home_marker(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""
    return normalize_text(PDF_LEADING_HOME_RE.sub("", cleaned))


def _is_ignorable_pdf_line(text: str) -> bool:
    folded = fold_text(text)
    return bool(
        PDF_HEADER_RE.match(text)
        or PDF_PAGE_ONLY_RE.match(text)
        or PDF_PAGE_LABEL_RE.match(text)
        or PDF_SEPARATOR_RE.match(text)
        or folded in PDF_EXACT_IGNORABLE_LINES
        or any(pattern.search(text) for pattern in PDF_IGNORABLE_LINE_PATTERNS)
    )


def _extract_page_lines(text: str) -> list[tuple[int, str]]:
    if PDF_EDOCS_SIGNATURE_PAGE_HINT_RE.search(text):
        return []

    lines: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        cleaned = _strip_inline_pdf_boilerplate(raw_line)
        if not cleaned or _is_ignorable_pdf_line(cleaned):
            continue
        lines.append((line_number, cleaned))
    return lines


def _clean_page_text(text: str) -> str:
    lines = [line for _, line in _extract_page_lines(text)]
    if lines:
        return _strip_leading_home_marker(" ".join(lines))
    return _strip_leading_home_marker(_strip_inline_pdf_boilerplate(text))


def _extract_records(page_texts: list[str]) -> list[StructuredTextRecord]:
    records: list[StructuredTextRecord] = []
    for page_idx, text in enumerate(page_texts, start=1):
        for line_number, line in _extract_page_lines(text):
            records.append(
                StructuredTextRecord(
                    text=line,
                    locator={
                        "page": page_idx,
                        "sheet": None,
                        "line_start": line_number,
                        "line_end": line_number,
                    },
                    extra={"page": page_idx},
                )
            )
    return records


def _extract_faq_question_match(text: str) -> tuple[int, int, str] | None:
    match = FAQ_QUESTION_RE.search(text)
    if match:
        question = normalize_text(match.group("question"))
        return match.start("question"), match.end("question"), question

    question_end = text.find("?")
    if question_end == -1 or question_end > 360:
        return None

    before_question = text[: question_end + 1]
    article_matches = list(FAQ_ARTICLE_START_RE.finditer(before_question))
    for article_match in reversed(article_matches):
        candidate = normalize_text(before_question[article_match.start() :])
        if 24 <= len(candidate) <= 260:
            return article_match.start(), question_end + 1, candidate

    return None


def _extract_faq_question(text: str) -> str | None:
    question_match = _extract_faq_question_match(text)
    if not question_match:
        return None
    return question_match[2]


def _looks_like_faq_document(page_texts: list[str]) -> bool:
    if len(page_texts) > 4:
        return False

    cleaned_pages = [_clean_page_text(text) for text in page_texts]
    combined = normalize_text(" ".join(text for text in cleaned_pages if text))
    if not combined:
        return False

    question_match = _extract_faq_question_match(combined)
    if not question_match:
        return False

    question_start, _, question = question_match
    if question_start > 260:
        return False

    return 24 <= len(question) <= 260


def _build_faq_blocks(page_texts: list[str]) -> list[dict]:
    cleaned_pages = [_clean_page_text(text) for text in page_texts]
    combined = normalize_text(" ".join(text for text in cleaned_pages if text))
    question_match = _extract_faq_question_match(combined)
    if not question_match:
        return _build_page_blocks(page_texts)

    question_start, question_end, question_text = question_match
    leading_text = normalize_text(combined[:question_start]).strip(" -–:.;")
    answer_text = normalize_text(combined[question_end:]).strip(" -–:.;")

    blocks: list[dict] = []
    block_idx = 1

    if leading_text and len(leading_text) <= 160:
        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "heading",
                "title": make_preview_title(leading_text, max_length=120),
                "text": leading_text,
                "locator": {"page": 1, "sheet": None, "line_start": None, "line_end": None},
                "extra": {"heading_level": 1, "heading_group": "document_title", "qa_role": "title"},
            }
        )
        block_idx += 1

    blocks.append(
        {
            "id": f"block_{block_idx:04d}",
            "kind": "heading",
            "title": question_text,
            "text": question_text,
            "locator": {"page": 1, "sheet": None, "line_start": None, "line_end": None},
            "extra": {
                "heading_level": 2 if blocks else 1,
                "heading_group": "question",
                "qa_role": "question",
            },
        }
    )
    block_idx += 1

    if answer_text:
        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "paragraph",
                "title": make_preview_title(answer_text),
                "text": answer_text,
                "locator": {"page": 1, "sheet": None, "line_start": None, "line_end": None},
                "extra": {"manual_group": "answer", "qa_role": "answer"},
            }
        )

    return blocks


def _derive_page_block_title(cleaned_text: str, page_idx: int) -> str:
    question_title = _extract_faq_question(cleaned_text)
    if question_title:
        return question_title
    return f"Page {page_idx}"


def _build_page_blocks(page_texts: list[str]) -> list[dict]:
    blocks = []
    block_idx = 1

    for page_idx, text in enumerate(page_texts, start=1):
        cleaned = _clean_page_text(text)
        if not cleaned:
            continue

        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "page_text",
                "title": _derive_page_block_title(cleaned, page_idx),
                "text": cleaned,
                "locator": {"page": page_idx, "sheet": None, "line_start": None, "line_end": None},
                "extra": {},
            }
        )
        block_idx += 1

    return blocks


def _should_prefer_manual(record_texts: list[str]) -> bool:
    early_text = " ".join(normalize_text(text).lower() for text in record_texts[:10])
    title_hits = sum(1 for hint in MANUAL_TITLE_HINTS if hint in early_text)
    structure_hits = sum(1 for hint in MANUAL_STRUCTURE_HINTS if hint in early_text)
    operation_hits = sum(1 for hint in MANUAL_OPERATION_HINTS if hint in early_text)
    return title_hits >= 1 or structure_hits >= 2 or (structure_hits >= 1 and operation_hits >= 2)


def _extract_page_text(page) -> tuple[str, str]:
    try:
        return page.extract_text() or "", "default"
    except Exception:
        text = page.extract_text(extraction_mode="layout") or ""
        return text, "layout"


def build_blocks_from_page_texts(page_texts: list[str]) -> tuple[list[dict], str]:
    records = _extract_records(page_texts)
    record_texts = [record.text for record in records]
    if _looks_like_faq_document(page_texts):
        return _build_faq_blocks(page_texts), "structured_faq"
    is_manual_document = looks_like_manual_document(record_texts)
    is_legal_document = looks_like_legal_document(record_texts)
    if is_manual_document and (not is_legal_document or _should_prefer_manual(record_texts)):
        return build_manual_blocks(records), "structured_manual"
    if is_legal_document:
        return build_legal_blocks(records), "structured_legal"
    return _build_page_blocks(page_texts), "page_text"


def parse_pdf(path: Path) -> dict:
    reader = PdfReader(str(path))
    page_texts: list[str] = []
    fallback_pages = 0
    failed_pages: list[int] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            text, strategy = _extract_page_text(page)
            if strategy != "default":
                fallback_pages += 1
            page_texts.append(text)
        except Exception:
            failed_pages.append(page_idx)
            page_texts.append("")

    if not any(text.strip() for text in page_texts):
        failed_page_list = ", ".join(str(page) for page in failed_pages) if failed_pages else "desconhecidas"
        raise ValueError(f"nao foi possivel extrair texto do PDF; paginas com falha: {failed_page_list}")

    blocks, mode = build_blocks_from_page_texts(page_texts)

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "page_count": len(reader.pages),
                "block_count": len(blocks),
                "mode": mode,
                "fallback_pages": fallback_pages,
                "failed_pages": failed_pages,
                "kind_counts": dict(sorted(Counter(block["kind"] for block in blocks).items())),
            },
        }
    }
