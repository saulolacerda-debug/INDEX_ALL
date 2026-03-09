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
LETTERED_LIST_RE = re.compile(r"^(?P<identifier>[a-z])\)\s+(?P<body>.+)$", re.IGNORECASE)
NUMBERED_LIST_RE = re.compile(r"^(?P<identifier>\d+)[\.\)-]\s+(?P<body>.+)$")
ORDINAL_LIST_RE = re.compile(r"^(?P<identifier>\d+(?:º|°|o)?)\s*[\)\-–]\s+(?P<body>.+)$", re.IGNORECASE)
INTERFACE_LABEL_RE = re.compile(
    r"^(?:portal|painel|menu|aba|bot[aã]o|campo|tela|filtro|consulta|op[cç][aã]o|minhas apura[cç][oõ]es)\b",
    re.IGNORECASE,
)
MICRO_ACTION_RE = re.compile(
    r"^(?:clique|acesse|acessar|selecione|preencha|informe|digite|escolha|utilize|verifique|confira|envie|registre)\b",
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
ARTICLE_REFERENCE_PREFIXES = (
    "da ",
    "das ",
    "de ",
    "desta ",
    "deste ",
    "do ",
    "dos ",
    "na ",
    "nas ",
    "no ",
    "nos ",
    "todos ",
    "todas ",
    "ambos ",
    "ambas ",
    "referido ",
    "referida ",
    "previsto ",
    "prevista ",
    "nos termos ",
    "na forma ",
)
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


def _normalize_locator_bounds(locator: dict) -> dict:
    normalized = dict(locator)
    line_start = normalized.get("line_start")
    line_end = normalized.get("line_end")
    if isinstance(line_start, int) and isinstance(line_end, int) and line_end < line_start:
        normalized["line_end"] = line_start
    return normalized


def _merge_record_locator(first_record: StructuredTextRecord, last_record: StructuredTextRecord) -> dict:
    locator = {
        "page": first_record.locator.get("page"),
        "sheet": first_record.locator.get("sheet"),
        "line_start": first_record.locator.get("line_start"),
        "line_end": _resolved_line_end(last_record.locator),
    }

    first_page = first_record.locator.get("page")
    last_page = last_record.locator.get("page")
    if first_page is not None and last_page is not None and first_page != last_page:
        locator["line_end"] = _resolved_line_end(first_record.locator)

    return _normalize_locator_bounds(locator)


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


def _looks_like_sentence_continuation(text: str | None) -> bool:
    if not text:
        return False
    cleaned = clean_label_text(text)
    if not cleaned:
        return False
    if classify_normative_text(cleaned):
        return False
    return cleaned[-1].islower() or cleaned.endswith((",", "-", "–"))


def _looks_like_article_reference_remainder(text: str | None) -> bool:
    if not text:
        return False
    normalized = clean_label_text(text.lstrip(" -–:.;,"))
    folded = fold_text(normalized)
    if not folded:
        return False
    if any(folded.startswith(prefix) for prefix in ARTICLE_REFERENCE_PREFIXES):
        return True
    if normalized and normalized[0].islower() and not folded.startswith(
        (
            "fica ",
            "ficam ",
            "revoga ",
            "revogam ",
            "altera ",
            "alteram ",
            "institui ",
            "instituem ",
            "dispoe ",
            "dispoem ",
            "passa ",
            "passam ",
            "entra ",
            "entram ",
            "produz ",
            "produzem ",
            "e ",
            "sera ",
            "serao ",
            "sao ",
            "compete ",
            "cabera ",
            "cabe ",
            "esta ",
            "este ",
            "o ",
            "os ",
            "a ",
            "as ",
        )
    ):
        return True
    return False


def _is_real_article_heading(
    cleaned: str,
    match: re.Match[str],
    *,
    continuation_text: str | None = None,
    previous_text: str | None = None,
) -> bool:
    if cleaned.startswith("art."):
        return False

    remainder = cleaned[match.end() :].strip()
    if _looks_like_article_reference_remainder(remainder):
        return False
    if _looks_like_sentence_continuation(previous_text) and _looks_like_article_reference_remainder(remainder or continuation_text):
        return False
    return True


def _is_manual_document_title(text: str, context: dict[str, int | str | None] | None) -> bool:
    folded = fold_text(text)
    if "manual" not in folded:
        return False
    if context and isinstance(context.get("last_heading_level"), int):
        return False
    return len(text.split()) <= 14


def _is_manual_interface_heading(text: str) -> bool:
    cleaned = clean_label_text(text).strip(":-–")
    if not cleaned:
        return False
    if INTERFACE_LABEL_RE.match(cleaned):
        return True
    return "-" not in cleaned and _is_all_caps_heading(cleaned) and any(
        token in fold_text(cleaned)
        for token in ("portal", "painel", "menu", "botao", "tela", "consulta", "apura")
    )


def _is_manual_micro_action(text: str) -> bool:
    return bool(MICRO_ACTION_RE.match(clean_label_text(text)))


def _is_manual_list_item(text: str) -> bool:
    cleaned = clean_label_text(text)
    if LETTERED_LIST_RE.match(cleaned):
        return True
    match = NUMBERED_LIST_RE.match(cleaned) or ORDINAL_LIST_RE.match(cleaned)
    if not match:
        return False
    body = normalize_text(match.group("body"))
    return bool(body) and (body[0].islower() or _is_manual_micro_action(body))


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
    previous_text: str | None = None,
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
    if match and _is_real_article_heading(
        cleaned,
        match,
        continuation_text=continuation_text,
        previous_text=previous_text,
    ):
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
    previous_text: str | None = None,
    context: dict[str, str | None] | None = None,
) -> Classification:
    normative = classify_normative_text(
        text,
        continuation_text,
        previous_text=previous_text,
        context=context,
    )
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

    if _is_manual_document_title(cleaned, context):
        return Classification(
            kind="heading",
            title=normalize_text(cleaned),
            heading_level=1,
            group="document_title",
        )

    if (
        context
        and not isinstance(context.get("last_heading_level"), int)
        and not _is_manual_marker_heading(cleaned)
        and not STEP_HEADING_RE.match(cleaned)
        and not _looks_like_numbered_manual_heading(cleaned)
        and not _is_manual_micro_action(cleaned)
        and (_is_all_caps_heading(cleaned) or _looks_like_short_manual_heading(cleaned))
    ):
        return Classification(
            kind="heading",
            title=normalize_text(cleaned),
            heading_level=1,
            group="document_title",
        )

    numbered_match = _looks_like_numbered_manual_heading(cleaned)
    if numbered_match:
        title_text = normalize_text(numbered_match.group("title")).lstrip("-–: ").strip()
        if _is_manual_micro_action(title_text):
            return Classification(kind="paragraph", title=make_preview_title(cleaned), group="micro_action")
        level = numbered_match.group("number").count(".") + 2
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

    if _is_manual_interface_heading(cleaned):
        return Classification(
            kind="paragraph",
            title=make_preview_title(cleaned, max_length=120),
            group="interface_label",
        )

    if _is_manual_micro_action(cleaned):
        return Classification(kind="paragraph", title=make_preview_title(cleaned), group="micro_action")

    if _is_manual_list_item(cleaned):
        return Classification(kind="paragraph", title=make_preview_title(cleaned), group="list_item")

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

        if _is_manual_micro_action(cleaned):
            structure_hits += 1
            continue

        if STEP_HEADING_RE.match(cleaned):
            structure_hits += 1
            continue

        if _looks_like_numbered_manual_heading(cleaned):
            structure_hits += 1
            continue

        if _is_manual_interface_heading(cleaned):
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
            locator=_normalize_locator_bounds(dict(record.locator or {})),
            extra=dict(record.extra or {}),
            style_name=record.style_name,
        )
        for record in records
        if normalize_text(record.text or "")
    ]

    classified_records: list[tuple[StructuredTextRecord, Classification]] = []
    classification_context: dict[str, int | str | None] = {
        "last_heading_level": None,
        "last_heading_group": None,
    }
    for record in normalized_records:
        classification = classify_manual_text(record.text, style_name=record.style_name, context=classification_context)
        classified_records.append((record, classification))
        if classification.kind == "heading":
            classification_context["last_heading_level"] = classification.heading_level
            classification_context["last_heading_group"] = classification.group

    heading_title_counts = Counter(
        fold_text(classification.title or "")
        for _, classification in classified_records
        if classification.kind == "heading" and classification.title
    )
    overview_heading_indexes: set[int] = set()
    seen_heading_titles: set[str] = set()
    for index, (_, classification) in enumerate(classified_records):
        if classification.kind != "heading" or not classification.title:
            continue
        heading_key = fold_text(classification.title)
        if (
            index <= 12
            and heading_title_counts.get(heading_key, 0) >= 2
            and heading_key not in seen_heading_titles
            and classification.group in {"numbered_heading", "primary_heading", "marker"}
            and (classification.heading_level or 0) <= 3
        ):
            overview_heading_indexes.add(index)
        seen_heading_titles.add(heading_key)

    early_numbered_cluster: list[int] = []
    last_cluster_number: tuple[int, ...] | None = None
    for index, (_, classification) in enumerate(classified_records):
        if index > 20:
            break
        if classification.kind == "heading" and classification.group == "numbered_heading":
            label = str(classification.label or "")
            try:
                current_number = tuple(int(part) for part in label.split("."))
            except ValueError:
                current_number = None
            if (
                early_numbered_cluster
                and current_number is not None
                and last_cluster_number is not None
                and current_number <= last_cluster_number
            ):
                break
            early_numbered_cluster.append(index)
            if current_number is not None:
                last_cluster_number = current_number
            continue
        if early_numbered_cluster:
            break
    if len(early_numbered_cluster) >= 3 and any(
        classification.kind == "heading" and classification.group == "numbered_heading"
        for _, classification in classified_records[early_numbered_cluster[-1] + 1 :]
    ):
        overview_heading_indexes.update(early_numbered_cluster)

    blocks: list[dict] = []
    block_idx = 1
    paragraph_buffer: list[StructuredTextRecord] = []
    paragraph_group: str | None = None

    def flush_paragraph_buffer() -> None:
        nonlocal block_idx, paragraph_buffer, paragraph_group

        if not paragraph_buffer:
            return

        merged_text = normalize_text(" ".join(record.text for record in paragraph_buffer))
        if not merged_text:
            paragraph_buffer = []
            return

        first_record = paragraph_buffer[0]
        last_record = paragraph_buffer[-1]
        extra = dict(first_record.extra)
        if paragraph_group:
            extra["manual_group"] = paragraph_group
        if len(paragraph_buffer) > 1:
            extra["segment_count"] = len(paragraph_buffer)

        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "paragraph",
                "title": make_preview_title(merged_text),
                "text": merged_text,
                "locator": _merge_record_locator(first_record, last_record),
                "extra": extra,
            }
        )
        block_idx += 1
        paragraph_buffer = []
        paragraph_group = None

    def append_single_paragraph(record: StructuredTextRecord, group: str) -> None:
        nonlocal block_idx

        extra = dict(record.extra)
        extra["manual_group"] = group
        blocks.append(
            {
                "id": f"block_{block_idx:04d}",
                "kind": "paragraph",
                "title": make_preview_title(record.text),
                "text": record.text,
                "locator": _normalize_locator_bounds(dict(record.locator)),
                "extra": extra,
            }
        )
        block_idx += 1

    for index, (record, classification) in enumerate(classified_records):
        if paragraph_buffer and paragraph_buffer[0].locator.get("page") != record.locator.get("page"):
            flush_paragraph_buffer()

        if index in overview_heading_indexes:
            if paragraph_group not in {None, "overview"}:
                flush_paragraph_buffer()
            paragraph_buffer.append(
                StructuredTextRecord(
                    text=record.text,
                    locator=dict(record.locator),
                    extra={**record.extra, "manual_group": "overview"},
                    style_name=record.style_name,
                )
            )
            paragraph_group = "overview"
            continue

        if classification.kind == "heading":
            flush_paragraph_buffer()

            extra = dict(record.extra)
            extra["manual_group"] = classification.group
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
                    "locator": _normalize_locator_bounds(dict(record.locator)),
                    "extra": extra,
                }
            )
            block_idx += 1
            continue

        if classification.group in {"list_item", "micro_action", "interface_label"}:
            flush_paragraph_buffer()
            append_single_paragraph(record, classification.group)
            continue

        if paragraph_group and paragraph_group != classification.group:
            flush_paragraph_buffer()

        paragraph_buffer.append(record)
        paragraph_group = classification.group or "body"

    flush_paragraph_buffer()
    return blocks


def build_legal_blocks(records: Sequence[StructuredTextRecord]) -> list[dict]:
    normalized_records = [
        StructuredTextRecord(
            text=normalize_text(record.text or ""),
            locator=_normalize_locator_bounds(dict(record.locator or {})),
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
    buffer_start_index: int | None = None
    heading_continuation_count = 0

    def reset_buffer() -> None:
        nonlocal buffered_records, buffer_classification, buffer_start_index, heading_continuation_count
        buffered_records = []
        buffer_classification = None
        buffer_start_index = None
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
        merged_locator = _merge_record_locator(first_record, last_record)
        previous_text = normalized_records[buffer_start_index - 1].text if isinstance(buffer_start_index, int) and buffer_start_index > 0 else None

        if buffer_classification is None and not seen_structure:
            classification = Classification(kind="preamble", title="Preâmbulo", label="Preâmbulo")
        else:
            classification = classify_paragraph(
                merged_text,
                style_name=first_record.style_name,
                previous_text=previous_text,
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
                    line_start=merged_locator.get("line_start"),
                    line_end=merged_locator.get("line_end"),
                ),
                "extra": extra,
            }
        )
        block_idx += 1
        reset_buffer()

    for index, record in enumerate(normalized_records):
        next_text = normalized_records[index + 1].text if index + 1 < len(normalized_records) else None
        previous_text = normalized_records[index - 1].text if index > 0 else None
        line_classification = classify_normative_text(
            record.text,
            continuation_text=next_text,
            previous_text=previous_text,
            context=context,
        )

        if buffered_records and line_classification:
            flush_buffer()

        if not buffered_records:
            buffered_records = [record]
            buffer_classification = line_classification
            buffer_start_index = index
            continue

        is_heading_buffer = bool(buffer_classification and buffer_classification.kind in HEADING_STRUCTURAL_KINDS)
        if is_heading_buffer and heading_continuation_count >= 1 and not line_classification:
            flush_buffer()
            buffered_records = [record]
            buffer_classification = line_classification
            buffer_start_index = index
            continue

        buffered_records.append(record)
        if is_heading_buffer and not line_classification:
            heading_continuation_count += 1

    flush_buffer()
    return blocks
