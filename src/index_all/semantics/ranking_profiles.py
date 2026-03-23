from __future__ import annotations


DEFAULT_RANKING_PROFILE = "legal"
RANKING_PROFILES = ("legal", "generic")

_LEGAL_ARCHETYPE_BONUS = {
    "legislation_normative": 0.9,
    "legislation_amending_act": 0.9,
    "manual_procedural": 0.8,
    "judicial_case": 0.75,
    "spreadsheet_structured": 0.55,
    "xml_structured": 0.55,
    "financial_statement_ofx": 0.55,
}
_GENERIC_ARCHETYPE_BONUS = {
    "legislation_normative": 0.18,
    "legislation_amending_act": 0.18,
    "manual_procedural": 0.16,
    "judicial_case": 0.16,
    "spreadsheet_structured": 0.14,
    "xml_structured": 0.14,
    "financial_statement_ofx": 0.14,
}

_RERANK_WEIGHTS = {
    "legal": {
        "textual": 42.0,
        "vector": 24.0,
        "legal_reference": 18.0,
        "heading": 10.0,
        "document_archetype": 6.0,
        "source_kind": 3.0,
        "chunk_size": 5.0,
    },
    "generic": {
        "textual": 42.0,
        "vector": 24.0,
        "legal_reference": 0.0,
        "heading": 10.0,
        "document_archetype": 2.0,
        "source_kind": 3.0,
        "chunk_size": 5.0,
    },
}


def normalize_ranking_profile(profile: str | None) -> str:
    candidate = str(profile or DEFAULT_RANKING_PROFILE).strip().lower()
    if candidate not in RANKING_PROFILES:
        valid_profiles = ", ".join(RANKING_PROFILES)
        raise ValueError(f"Unsupported ranking profile: {profile!r}. Expected one of: {valid_profiles}.")
    return candidate


def rerank_weights(profile: str | None) -> dict[str, float]:
    return dict(_RERANK_WEIGHTS[normalize_ranking_profile(profile)])


def archetype_bonus_map(profile: str | None) -> dict[str, float]:
    normalized = normalize_ranking_profile(profile)
    if normalized == "generic":
        return dict(_GENERIC_ARCHETYPE_BONUS)
    return dict(_LEGAL_ARCHETYPE_BONUS)


def uses_legal_reference_scoring(profile: str | None) -> bool:
    return normalize_ranking_profile(profile) == "legal"
