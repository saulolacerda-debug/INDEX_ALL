from __future__ import annotations

import re
import unicodedata
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
NUMBERED_SECTION_RE = re.compile(r"^(?P<number>\d+(?:\.\d+){0,4})(?:\.)?\s+(?P<title>.+)$")
STEP_HEADING_RE = re.compile(
    r"^(?P<label>ETAPA|PASSO|FASE)\s+(?P<identifier>[0-9IVXLCDM]+)\b(?:\s*[-–:]\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

MANUAL_MARKER_TITLES = {
    "escopo",
    "etapa",
    "etapas",
    "finalidade",
    "fluxo",
    "introducao",
    "objetivo",
    "objetivos",
    "passo a passo",
    "passos",
    "procedimento",
    "procedimentos",
    "resumo",
    "visao geral",
}
AMENDMENT_CONTEXT_HINTS = (
    "acrescenta",
    "altera",
    "com a seguinte redacao",
    "com as seguintes alteracoes",
    "da nova redacao",
    "fica acrescido",
    "passa a vigorar com",
    "passam a vigorar com",
    "renumera",
)


@dataclass(frozen=True)
class Classification:
    kind: str
    title: str | None
    label: str | None = None
    locator_key: str | None = None
    heading_level: int | None = None
    group: str | None = None


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


def fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(text).lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


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


def text_starts_with_quote(text: str) -> bool:
    stripped = str(text or "").lstrip()
    return bool(stripped) and stripped[0] in {'"', "“", "”"}


def text_indicates_amendment_context(text: str) -> bool:
    folded = fold_text(text)
    return any(hint in folded for hint in AMENDMENT_CONTEXT_HINTS)


def _is_manual_marker_heading(text: str) -> bool:
    marker = fold_text(text).strip(" :-–.;")
    return marker in MANUAL_MARKER_TITLES


def _looks_like_short_manual_heading(text: str) -> bool:
    cleaned = clean_label_text(text).strip(":-–")
    if not cleaned or len(cleaned) > 80 or cleaned.endswith((".", ";")):
        return False
    if classify_normative_text(cleaned):
        return False

    words = [word for word in cleaned.split() if any(character.isalpha() for character in word)]
    if not 2 <= len(words) <= 8:
        return False

    title_case_words = sum(
        1
        for word in words
        if word[0].isupper() and not word.isupper()
    )
    return title_case_words >= max(2, len(words) - 1)


def _is_all_caps_heading(text: str) -> bool:
    cleaned = clean_label_text(text).strip(":-–")
    if not cleaned or len(cleaned) > 96 or cleaned.endswith((".", ";")):
        return False
    if classify_normative_text(cleaned):
        return False

    letters = [character for character in cleaned if character.isalpha()]
    if len(letters) < 4:
        return False

    uppercase_ratio = sum(character.isupper() for character in letters) / len(letters)
    return uppercase_ratio >= 0.72


def _looks_like_numbered_manual_heading(text: str) -> re.Match[str] | None:
    match = NUMBERED_SECTION_RE.match(clean_label_text(text))
    if not match:
        return None

    title = normalize_text(match.group("title"))
    number = match.group("number")
    if not title or len(title) > 96:
        return None
    if title.endswith((".", ";")) and "." not in number:
        return None
    if title and title[0].islower():
        return None
    return match


def _resolve_manual_heading_level(
    group: str,
    context: dict[str, int | str | None] | None,
    *,
    explicit_level: int | None = None,
) -> int:
    if explicit_level is not None:
        return max(1, min(explicit_level, 6))

    last_level = context.get("last_heading_level") if context else None
    last_group = context.get("last_heading_group") if context else None

    if not isinstance(last_level, int):
        return 1

    if group == "marker":
        if last_group == "marker":
            return last_level
        if last_group == "step":
            return max(last_level - 1, 2)
        return min(last_level + 1, 6)

    if group == "step":
        if last_group == "step":
            return last_level
        return min(last_level + 1, 6)

    if group == "primary_heading":
        if last_group in {"marker", "step"}:
            return max(last_level - 1, 1)
        if last_level == 1:
            return 2
        return last_level

    return last_level


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


def classify_manual_text(
    text: str,
    *,
    style_name: str | None = None,
    context: dict[str, int | str | None] | None = None,
) -> Classification:
    cleaned = clean_label_text(text)
    if not cleaned:
        return Classification(kind="paragraph", title=None, group="body")

    heading_level = extract_heading_level(style_name)
    if heading_level is not None:
        return Classification(
            kind="heading",
            title=make_preview_title(cleaned, max_length=120),
            heading_level=_resolve_manual_heading_level("styled_heading", context, explicit_level=heading_level),
            group="styled_heading",
        )

    numbered_match = _looks_like_numbered_manual_heading(cleaned)
    if numbered_match:
        level = numbered_match.group("number").count(".") + 1
        return Classification(
            kind="heading",
            title=normalize_text(cleaned),
            label=numbered_match.group("number"),
            heading_level=_resolve_manual_heading_level("numbered_heading", context, explicit_level=level),
            group="numbered_heading",
        )

    step_match = STEP_HEADING_RE.match(cleaned)
    if step_match:
        label = normalize_text(step_match.group("label")).capitalize()
        identifier = step_match.group("identifier").upper()
        remainder = normalize_text(step_match.group("title") or "")
        title = f"{label} {identifier}"
        if remainder:
            title = f"{title} - {remainder}"
        return Classification(
            kind="heading",
            title=title,
            label=title,
            heading_level=_resolve_manual_heading_level("step", context),
            group="step",
        )

    if _is_manual_marker_heading(cleaned):
        return Classification(
            kind="heading",
            title=normalize_text(cleaned.rstrip(":")),
            label=normalize_text(cleaned.rstrip(":")),
            heading_level=_resolve_manual_heading_level("marker", context),
            group="marker",
        )

    if _is_all_caps_heading(cleaned) or _looks_like_short_manual_heading(cleaned):
        return Classification(
            kind="heading",
            title=make_preview_title(cleaned, max_length=120),
            heading_level=_resolve_manual_heading_level("primary_heading", context),
            group="primary_heading",
        )

    return Classification(kind="paragraph", title=make_preview_title(cleaned), group="body")


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


def looks_like_manual_document(texts: Sequence[str]) -> bool:
    manual_hits = 0
    structure_hits = 0

    for text in texts:
        cleaned = clean_label_text(text)
        if not cleaned or classify_normative_text(cleaned):
            continue

        if "manual" in fold_text(cleaned) and len(cleaned.split()) <= 8:
            manual_hits += 1
            continue

        if _is_manual_marker_heading(cleaned):
            manual_hits += 1
            continue

        if STEP_HEADING_RE.match(cleaned):
            structure_hits += 1
            continue

        if _looks_like_numbered_manual_heading(cleaned):
            structure_hits += 1
            continue

        if _is_all_caps_heading(cleaned) or _looks_like_short_manual_heading(cleaned):
            structure_hits += 1

    if manual_hits >= 2:
        return True
    if manual_hits >= 1 and structure_hits >= 2:
        return True
    if structure_hits >= 4:
        return True
    return False


def _resolved_line_end(locator: dict) -> int | None:
    return locator.get("line_end") if locator.get("line_end") is not None else locator.get("line_start")


def build_manual_blocks(records: Sequence[StructuredTextRecord]) -> list[dict]:
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
    context: dict[str, int | str | None] = {
        "last_heading_level": None,
        "last_heading_group": None,
    }
    paragraph_buffer: list[StructuredTextRecord] = []

    def flush_paragraph_buffer() -> None:
        nonlocal block_idx, paragraph_buffer

        if not paragraph_buffer:
            return

        merged_text = normalize_text(" ".join(record.text for record in paragraph_buffer))
        if not merged_text:
            paragraph_buffer = []
            return

        first_record = paragraph_buffer[0]
        last_record = paragraph_buffer[-1]
        extra = dict(first_record.extra)
        if len(paragraph_buffer) > 1:
            extra["segment_count"] = len(paragraph_buffer)

        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "paragraph",
                "title": make_preview_title(merged_text),
                "text": merged_text,
                "locator": {
                    "page": first_record.locator.get("page"),
                    "sheet": first_record.locator.get("sheet"),
                    "line_start": first_record.locator.get("line_start"),
                    "line_end": _resolved_line_end(last_record.locator),
                },
                "extra": extra,
            }
        )
        block_idx += 1
        paragraph_buffer = []

    for record in normalized_records:
        classification = classify_manual_text(record.text, style_name=record.style_name, context=context)

        if classification.kind == "heading":
            flush_paragraph_buffer()

            extra = dict(record.extra)
            if classification.heading_level is not None:
                extra["heading_level"] = classification.heading_level
            if classification.group:
                extra["heading_group"] = classification.group
            if classification.label:
                extra["label"] = classification.label

            blocks.append(
                {
                    "id": f"block_{block_idx:04d}",
                    "kind": "heading",
                    "title": classification.title,
                    "text": record.text,
                    "locator": dict(record.locator),
                    "extra": extra,
                }
            )
            block_idx += 1
            context["last_heading_level"] = classification.heading_level
            context["last_heading_group"] = classification.group
            continue

        paragraph_buffer.append(record)

    flush_paragraph_buffer()
    return blocks


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
        if text_indicates_amendment_context(merged_text):
            extra["amendment_context"] = True
        if text_starts_with_quote(first_record.text):
            extra["starts_with_quote"] = True
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
