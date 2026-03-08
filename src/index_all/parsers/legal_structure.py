from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence


LEVEL_IDENTIFIER_RE = r"(?:[IVXLCDM0-9]+(?:-[A-Z0-9]+)?|ÚNICA|UNICA)"
PART_IDENTIFIER_RE = (
    r"(?:"
    r"[IVXLCDM0-9]+(?:-[A-Z0-9]+)?"
    r"|ÚNICA|UNICA|GERAL|ESPECIAL|PRELIMINAR(?:ES)?"
    r"|PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|S[ÉE]TIMA|OITAVA|NONA|D[ÉE]CIMA"
    r")"
)

STRUCTURE_CONTEXT_KEYS = (
    "part",
    "book",
    "title",
    "chapter",
    "section",
    "subsection",
    "article",
    "paragraph",
    "inciso",
    "alinea",
    "item",
)

CONTEXT_RESET_RULES: dict[str, tuple[str, ...]] = {
    "part": ("book", "title", "chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item"),
    "book": ("title", "chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item"),
    "title": ("chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item"),
    "chapter": ("section", "subsection", "article", "paragraph", "inciso", "alinea", "item"),
    "section": ("subsection", "article", "paragraph", "inciso", "alinea", "item"),
    "subsection": ("article", "paragraph", "inciso", "alinea", "item"),
    "article": ("paragraph", "inciso", "alinea", "item"),
    "paragraph": ("inciso", "alinea", "item"),
    "inciso": ("alinea", "item"),
    "alinea": ("item",),
    "item": (),
}

STRUCTURAL_KINDS = {
    "part",
    "book",
    "title",
    "chapter",
    "section",
    "subsection",
    "article",
    "legal_paragraph",
    "inciso",
    "alinea",
    "item",
}
MAJOR_STRUCTURAL_KINDS = {
    "part",
    "book",
    "title",
    "chapter",
    "section",
    "subsection",
    "article",
    "legal_paragraph",
}
HEADING_STRUCTURAL_KINDS = {"part", "book", "title", "chapter", "section", "subsection"}

ARTICLE_RE = re.compile(
    r'^(?:["“”]\s*)?Art\.\s*(?P<identifier>\d+(?:-[A-Z])?(?:º|°|o)?)\.?',
    re.IGNORECASE,
)
UNIQUE_PARAGRAPH_RE = re.compile(r'^(?:["“”]\s*)?Par[áa]grafo\s+[úu]nico\.?', re.IGNORECASE)
LEGAL_PARAGRAPH_RE = re.compile(
    r'^(?:["“”]\s*)?§\s*(?P<identifier>\d+(?:-[A-Z])?(?:º|°|o)?)',
    re.IGNORECASE,
)
INCISO_RE = re.compile(r'^(?:["“”]\s*)?(?P<identifier>[IVXLCDM]+)\s*[-–]', re.IGNORECASE)
ALINEA_RE = re.compile(r'^(?:["“”]\s*)?(?P<identifier>[a-z])\)\s*', re.IGNORECASE)
ITEM_RE = re.compile(r'^(?:["“”]\s*)?(?P<identifier>\d+)\s*[\.\)-]\s+')
PART_RE = re.compile(rf'^(?:["“”]\s*)?PARTE\s+(?P<identifier>{PART_IDENTIFIER_RE})\b', re.IGNORECASE)
BOOK_RE = re.compile(rf'^(?:["“”]\s*)?LIVRO\s+(?P<identifier>{LEVEL_IDENTIFIER_RE})\b', re.IGNORECASE)
TITLE_RE = re.compile(rf'^(?:["“”]\s*)?T[ÍI]TULO\s+(?P<identifier>{LEVEL_IDENTIFIER_RE})\b', re.IGNORECASE)
CHAPTER_RE = re.compile(rf'^(?:["“”]\s*)?CAP[ÍI]TULO\s+(?P<identifier>{LEVEL_IDENTIFIER_RE})\b', re.IGNORECASE)
SECTION_RE = re.compile(rf'^(?:["“”]\s*)?SE(?:ÇÃO|CAO)\s+(?P<identifier>{LEVEL_IDENTIFIER_RE})\b', re.IGNORECASE)
SUBSECTION_RE = re.compile(rf'^(?:["“”]\s*)?SUBSE(?:ÇÃO|CAO)\s+(?P<identifier>{LEVEL_IDENTIFIER_RE})\b', re.IGNORECASE)
LEGAL_DOCUMENT_TITLE_RE = re.compile(
    r"^(?:LEI(?:\s+COMPLEMENTAR)?|DECRETO(?:-LEI)?|EMENDA\s+CONSTITUCIONAL|CONSTITUIÇÃO|MEDIDA\s+PROVISÓRIA|PORTARIA|RESOLUÇÃO|INSTRUÇÃO\s+NORMATIVA|CÓDIGO)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Classification:
    kind: str
    title: str | None
    label: str | None = None
    locator_key: str | None = None
    heading_level: int | None = None


@dataclass(frozen=True)
class StructuredTextRecord:
    text: str
    locator: dict
    extra: dict
    style_name: str | None = None


def new_structure_context() -> dict[str, str | None]:
    return {key: None for key in STRUCTURE_CONTEXT_KEYS}


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def clean_label_text(text: str) -> str:
    return normalize_text(text).lstrip('"“”').strip()


def make_preview_title(text: str, max_length: int = 90) -> str:
    preview = normalize_text(text)
    if len(preview) <= max_length:
        return preview
    return f"{preview[: max_length - 3].rstrip()}..."


def summarize_article_text(text: str, max_words: int = 12, max_length: int = 88) -> str | None:
    cleaned = clean_label_text(text)
    match = ARTICLE_RE.match(cleaned)
    if not match:
        return None

    remainder = cleaned[match.end() :].strip(" -–:.;")
    if not remainder:
        return None

    sentence_parts = re.split(r"(?<=[;:!?])\s+", remainder, maxsplit=1)
    summary = sentence_parts[0].strip(" -–:.;")
    if len(summary) > max_length:
        comma_parts = re.split(r",\s+", summary)
        compact = comma_parts[0].strip(" -–:.;")
        if compact and len(compact.split()) >= 6:
            summary = compact

    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]).rstrip(",;:.") + "..."
    elif len(summary) > max_length:
        summary = summary[: max_length - 3].rstrip(",;: ") + "..."

    return summary or None


def extract_heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None

    word_match = re.search(r"\b[hH]([1-6])\b", style_name)
    if word_match:
        return int(word_match.group(1))

    match = re.search(r"Heading\s*(\d+)", style_name, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _normalize_heading_identifier(identifier: str) -> str:
    parts = []
    for part in clean_label_text(identifier).split():
        if re.fullmatch(r"[IVXLCDM0-9]+(?:-[A-Z0-9]+)?", part, re.IGNORECASE):
            parts.append(part.upper())
        else:
            parts.append(part.capitalize())
    return " ".join(parts)


def _looks_like_heading_continuation(text: str | None) -> bool:
    if not text:
        return False
    cleaned = clean_label_text(text)
    if not cleaned or len(cleaned) > 180:
        return False
    if cleaned.endswith((".", ";")):
        return False
    if classify_normative_text(cleaned):
        return False
    return any(character.isalpha() for character in cleaned)


def _format_heading_title(
    prefix: str,
    identifier: str,
    remainder: str,
    continuation_text: str | None,
) -> str:
    base = f"{prefix} {identifier}"
    if remainder:
        return f"{base} - {remainder}"
    if _looks_like_heading_continuation(continuation_text):
        return f"{base} - {clean_label_text(continuation_text)}"
    return base


def classify_normative_text(
    text: str,
    continuation_text: str | None = None,
    context: dict[str, str | None] | None = None,
) -> Classification | None:
    cleaned = clean_label_text(text)
    if not cleaned:
        return None

    for regex, kind, prefix, locator_key in (
        (PART_RE, "part", "Parte", "part"),
        (BOOK_RE, "book", "Livro", "book"),
        (TITLE_RE, "title", "Título", "title"),
        (CHAPTER_RE, "chapter", "Capítulo", "chapter"),
        (SECTION_RE, "section", "Seção", "section"),
        (SUBSECTION_RE, "subsection", "Subseção", "subsection"),
    ):
        match = regex.match(cleaned)
        if not match:
            continue
        identifier = _normalize_heading_identifier(match.group("identifier"))
        remainder = cleaned[match.end() :].strip(" -–:.;")
        title = _format_heading_title(prefix, identifier, remainder, continuation_text)
        return Classification(kind=kind, title=title, label=f"{prefix} {identifier}", locator_key=locator_key)

    match = ARTICLE_RE.match(cleaned)
    if match:
        identifier = match.group("identifier")
        return Classification(
            kind="article",
            title=f"Art. {identifier}",
            label=f"Art. {identifier}",
            locator_key="article",
        )

    if UNIQUE_PARAGRAPH_RE.match(cleaned):
        return Classification(
            kind="legal_paragraph",
            title="Parágrafo único",
            label="Parágrafo único",
            locator_key="paragraph",
        )

    match = LEGAL_PARAGRAPH_RE.match(cleaned)
    if match:
        identifier = match.group("identifier")
        return Classification(
            kind="legal_paragraph",
            title=f"§ {identifier}",
            label=f"§ {identifier}",
            locator_key="paragraph",
        )

    match = INCISO_RE.match(cleaned)
    if match:
        identifier = match.group("identifier").upper()
        return Classification(
            kind="inciso",
            title=f"Inciso {identifier}",
            label=f"Inciso {identifier}",
            locator_key="inciso",
        )

    match = ALINEA_RE.match(cleaned)
    if match:
        identifier = match.group("identifier").lower()
        return Classification(
            kind="alinea",
            title=f"Alínea {identifier}",
            label=f"Alínea {identifier}",
            locator_key="alinea",
        )

    if context and any(context.get(key) for key in ("alinea", "inciso", "paragraph", "article")):
        match = ITEM_RE.match(cleaned)
        if match:
            identifier = match.group("identifier")
            return Classification(
                kind="item",
                title=f"Item {identifier}",
                label=f"Item {identifier}",
                locator_key="item",
            )

    return None


def classify_paragraph(
    text: str,
    style_name: str | None = None,
    continuation_text: str | None = None,
    context: dict[str, str | None] | None = None,
) -> Classification:
    normative = classify_normative_text(text, continuation_text, context=context)
    if normative:
        return normative

    heading_level = extract_heading_level(style_name)
    if heading_level is not None:
        return Classification(kind="heading", title=make_preview_title(text, max_length=120), heading_level=heading_level)

    return Classification(kind="paragraph", title=make_preview_title(text))


def update_context(context: dict[str, str | None], classification: Classification) -> None:
    if not classification.locator_key or not classification.title:
        return

    context[classification.locator_key] = classification.title
    for key in CONTEXT_RESET_RULES.get(classification.locator_key, ()):
        context[key] = None


def build_locator(
    context: dict[str, str | None],
    *,
    page: int | None = None,
    sheet: str | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
) -> dict:
    locator = {
        "page": page,
        "sheet": sheet,
        "line_start": line_start,
        "line_end": line_end,
    }
    for key in STRUCTURE_CONTEXT_KEYS:
        locator[key] = context.get(key)
    return locator


def looks_like_legal_document(texts: Sequence[str]) -> bool:
    counts: Counter[str] = Counter()
    document_title_hits = 0

    for text in texts:
        cleaned = clean_label_text(text)
        if not cleaned:
            continue

        if LEGAL_DOCUMENT_TITLE_RE.match(cleaned):
            document_title_hits += 1

        classification = classify_normative_text(cleaned)
        if classification:
            counts[classification.kind] += 1

    heading_hits = sum(counts[kind] for kind in ("part", "book", "title", "chapter", "section", "subsection"))
    subordinate_hits = sum(counts[kind] for kind in ("legal_paragraph", "inciso", "alinea", "item"))

    if counts["article"] >= 2:
        return True
    if counts["article"] >= 1 and (heading_hits + subordinate_hits) >= 2:
        return True
    if document_title_hits >= 1 and counts["article"] >= 1:
        return True
    if heading_hits >= 2 and counts["article"] >= 1:
        return True
    if sum(counts[kind] for kind in MAJOR_STRUCTURAL_KINDS) >= 4:
        return True
    return False


def _resolved_line_end(locator: dict) -> int | None:
    return locator.get("line_end") if locator.get("line_end") is not None else locator.get("line_start")


def build_legal_blocks(records: Sequence[StructuredTextRecord]) -> list[dict]:
    normalized_records = [
        StructuredTextRecord(
            text=normalize_text(record.text or ""),
            locator=dict(record.locator or {}),
            extra=dict(record.extra or {}),
            style_name=record.style_name,
        )
        for record in records
        if normalize_text(record.text or "")
    ]

    blocks: list[dict] = []
    block_idx = 1
    context = new_structure_context()
    seen_structure = False
    buffered_records: list[StructuredTextRecord] = []
    buffer_classification: Classification | None = None
    heading_continuation_count = 0

    def reset_buffer() -> None:
        nonlocal buffered_records, buffer_classification, heading_continuation_count
        buffered_records = []
        buffer_classification = None
        heading_continuation_count = 0

    def flush_buffer() -> None:
        nonlocal block_idx, seen_structure

        if not buffered_records:
            return

        merged_text = normalize_text(" ".join(record.text for record in buffered_records))
        if not merged_text:
            reset_buffer()
            return

        first_record = buffered_records[0]
        last_record = buffered_records[-1]

        if buffer_classification is None and not seen_structure:
            classification = Classification(kind="preamble", title="Preâmbulo", label="Preâmbulo")
        else:
            classification = classify_paragraph(
                merged_text,
                style_name=first_record.style_name,
                context=context,
            )

        if classification.kind in STRUCTURAL_KINDS:
            seen_structure = True

        update_context(context, classification)

        extra = dict(first_record.extra)
        if classification.label:
            extra["label"] = classification.label
        if classification.heading_level is not None:
            extra["heading_level"] = classification.heading_level
        if len(buffered_records) > 1:
            extra["segment_count"] = len(buffered_records)
        if classification.kind == "article":
            article_summary = summarize_article_text(merged_text)
            if article_summary:
                extra["summary"] = article_summary
                extra["display_title"] = f"{classification.title} - {article_summary}"
                extra["index_title"] = extra["display_title"]

        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": classification.kind,
                "title": classification.title,
                "text": merged_text,
                "locator": build_locator(
                    context,
                    page=first_record.locator.get("page"),
                    sheet=first_record.locator.get("sheet"),
                    line_start=first_record.locator.get("line_start"),
                    line_end=_resolved_line_end(last_record.locator),
                ),
                "extra": extra,
            }
        )
        block_idx += 1
        reset_buffer()

    for index, record in enumerate(normalized_records):
        next_text = normalized_records[index + 1].text if index + 1 < len(normalized_records) else None
        line_classification = classify_normative_text(record.text, continuation_text=next_text, context=context)

        if buffered_records and line_classification:
            flush_buffer()

        if not buffered_records:
            buffered_records = [record]
            buffer_classification = line_classification
            continue

        is_heading_buffer = bool(buffer_classification and buffer_classification.kind in HEADING_STRUCTURAL_KINDS)
        if is_heading_buffer and heading_continuation_count >= 1 and not line_classification:
            flush_buffer()
            buffered_records = [record]
            buffer_classification = line_classification
            continue

        buffered_records.append(record)
        if is_heading_buffer and not line_classification:
            heading_continuation_count += 1

    flush_buffer()
    return blocks
