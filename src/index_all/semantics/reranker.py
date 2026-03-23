from __future__ import annotations

from typing import Any, Mapping, Sequence

from index_all.semantics.ranking_profiles import (
    DEFAULT_RANKING_PROFILE,
    archetype_bonus_map,
    normalize_ranking_profile,
    rerank_weights,
    uses_legal_reference_scoring,
)
from index_all.semantics.search_engine import (
    SOURCE_KIND_PRIORITY,
    extract_primary_legal_reference,
    legal_reference_details,
    normalize_text,
    query_tokens,
)

def _normalize_text_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return min(score / 72.0, 1.0)


def _normalize_vector_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return min(score, 1.0)


def _heading_signal(query: str, heading_path_text: str) -> float:
    normalized_heading = normalize_text(heading_path_text)
    if not normalized_heading:
        return 0.0

    normalized_query = normalize_text(query)
    tokens = list(dict.fromkeys(query_tokens(query)))
    if normalized_query and normalized_query in normalized_heading:
        return 1.0
    if not tokens:
        return 0.0

    hits = sum(1 for token in tokens if token in normalized_heading)
    return min(hits / max(len(tokens), 1), 1.0)


def _archetype_signal(query: str, document_archetype: str, ranking_profile: str) -> float:
    normalized_archetype = normalize_text(document_archetype).replace("_", " ")
    if not normalized_archetype:
        return 0.0

    bonus = archetype_bonus_map(ranking_profile).get(document_archetype, 0.12 if ranking_profile == "generic" else 0.3)
    tokens = list(dict.fromkeys(query_tokens(query)))
    if not tokens:
        return min(bonus, 1.0)

    hits = sum(1 for token in tokens if token in normalized_archetype)
    return min(bonus + (hits / max(len(tokens), 1)) * 0.4, 1.0)


def _source_kind_signal(source_kind: str) -> float:
    max_priority = max(SOURCE_KIND_PRIORITY.values()) if SOURCE_KIND_PRIORITY else 1
    return min(SOURCE_KIND_PRIORITY.get(source_kind, 1) / max_priority, 1.0)


def _chunk_size_signal(text_length: int) -> float:
    if text_length <= 0:
        return 0.0
    if 80 <= text_length <= 900:
        return 1.0
    if 40 <= text_length < 80 or 900 < text_length <= 1500:
        return 0.75
    if 20 <= text_length < 40 or 1500 < text_length <= 2200:
        return 0.45
    return 0.2


def _legal_reference_signal(query: str, heading_path_text: str, text: str = "") -> float:
    query_primary_refs = legal_reference_details(query)["query_references"]
    primary_heading_reference = extract_primary_legal_reference(heading_path_text.split(" > ")[-1] if heading_path_text else "")
    details = legal_reference_details(
        query,
        title=heading_path_text,
        heading_path=[heading_path_text] if heading_path_text else [],
        text=text,
    )
    if not details["query_references"]:
        return 0.0

    if primary_heading_reference and primary_heading_reference in query_primary_refs:
        return 1.0

    if primary_heading_reference and any(
        "-" in reference and reference.split("-", 1)[0] == primary_heading_reference for reference in query_primary_refs
    ):
        return 0.0

    mention_signal = (
        details["title_exact"] * 0.35
        + details["heading_exact"] * 0.25
        + details["body_exact"] * 0.1
    )
    mismatch_penalty = (
        details["title_partial_only"] * 0.35
        + details["heading_partial_only"] * 0.25
        + details["body_partial_only"] * 0.1
    )
    return max(min(mention_signal - mismatch_penalty, 0.45), 0.0)


def rerank_candidates(
    query: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    limit: int = 6,
    ranking_profile: str = DEFAULT_RANKING_PROFILE,
) -> list[dict]:
    normalized_profile = normalize_ranking_profile(ranking_profile)
    weights = rerank_weights(normalized_profile)
    reranked: list[dict] = []

    for candidate in candidates:
        text_score = float(candidate.get("text_score") or candidate.get("score") or 0.0)
        vector_score = float(candidate.get("vector_score") or 0.0)
        heading_path_text = str(candidate.get("heading_path_text") or "")
        document_archetype = str(candidate.get("document_archetype") or "")
        source_kind = str(candidate.get("source_kind") or "chunk")
        text = str(candidate.get("text") or "")
        text_length = int(candidate.get("text_length") or len(" ".join(str(candidate.get("text") or "").split())))

        components = {
            "textual": round(_normalize_text_score(text_score) * weights["textual"], 4),
            "vector": round(_normalize_vector_score(vector_score) * weights["vector"], 4),
            "legal_reference": round(
                (
                    _legal_reference_signal(query, heading_path_text, text)
                    if uses_legal_reference_scoring(normalized_profile)
                    else 0.0
                )
                * weights["legal_reference"],
                4,
            ),
            "heading": round(_heading_signal(query, heading_path_text) * weights["heading"], 4),
            "document_archetype": round(
                _archetype_signal(query, document_archetype, normalized_profile) * weights["document_archetype"],
                4,
            ),
            "source_kind": round(_source_kind_signal(source_kind) * weights["source_kind"], 4),
            "chunk_size": round(_chunk_size_signal(text_length) * weights["chunk_size"], 4),
        }
        final_score = round(sum(components.values()), 4)

        reranked.append(
            {
                **dict(candidate),
                "score": final_score,
                "score_breakdown": components,
                "text_score": round(text_score, 4),
                "vector_score": round(vector_score, 6),
                "text_length": text_length,
                "ranking_profile": normalized_profile,
                "retrieval_mode": "hybrid" if candidate.get("has_embedding") else "textual",
            }
        )

    sorted_results = sorted(
        reranked,
        key=lambda item: (
            -float(item["score"]),
            -float(item.get("text_score") or 0.0),
            -float(item.get("vector_score") or 0.0),
            int(item.get("text_length") or 0),
            str(item.get("file_name") or ""),
            str(item.get("heading_path_text") or ""),
        ),
    )
    return sorted_results[:limit]
