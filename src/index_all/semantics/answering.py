from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Sequence

from index_all.config import get_settings
from index_all.semantics.ranking_profiles import DEFAULT_RANKING_PROFILE, normalize_ranking_profile


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_MAX_GROUNDING_CHUNKS = 6


def _azure_openai_base_url(endpoint: str) -> str:
    normalized = str(endpoint or "").strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.endswith("/openai/v1"):
        return f"{normalized}/"
    if normalized.endswith("/openai"):
        return f"{normalized}/v1/"
    return f"{normalized}/openai/v1/"


def _missing_config_messages(settings: Any) -> list[str]:
    missing: list[str] = []
    if not getattr(settings, "azure_openai_endpoint", None):
        missing.append("INDEX_ALL_AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_ENDPOINT")
    if not getattr(settings, "azure_openai_api_key", None):
        missing.append("INDEX_ALL_AZURE_OPENAI_API_KEY/AZURE_OPENAI_API_KEY")
    if not getattr(settings, "azure_openai_deployment", None):
        missing.append("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT/AZURE_OPENAI_DEPLOYMENT")
    return missing


def _build_reference(chunk: Mapping[str, Any], citation_id: int) -> str:
    parts = [
        str(chunk.get("file_name") or "").strip(),
        str(chunk.get("heading_path_text") or "").strip(),
        str(chunk.get("locator_path") or chunk.get("position_text") or chunk.get("chunk_id") or "").strip(),
    ]
    compact_parts = [part for part in parts if part]
    if not compact_parts:
        compact_parts.append(f"chunk_{citation_id}")
    return " | ".join(compact_parts)


def build_grounding(query_results: Mapping[str, Any], *, max_chunks: int = _MAX_GROUNDING_CHUNKS) -> list[dict]:
    grounding: list[dict] = []
    for index, chunk in enumerate((query_results.get("chunks", []) or [])[: max(max_chunks, 1)], start=1):
        grounding.append(
            {
                "id": index,
                "chunk_id": chunk.get("chunk_id"),
                "file_name": chunk.get("file_name"),
                "file_type": chunk.get("file_type"),
                "document_archetype": chunk.get("document_archetype"),
                "heading_path_text": chunk.get("heading_path_text"),
                "locator_path": chunk.get("locator_path") or chunk.get("position_text"),
                "score": chunk.get("score"),
                "retrieval_mode": chunk.get("retrieval_mode"),
                "reference": _build_reference(chunk, index),
                "text": str(chunk.get("text") or ""),
            }
        )
    return grounding


def _answer_instructions() -> str:
    return (
        "Você é um assistente de análise documental do INDEX_ALL. "
        "Responda somente com base no grounding fornecido. "
        "Não invente fatos ausentes. "
        "Se o grounding não for suficiente, diga explicitamente a limitação. "
        "Use citações no formato [n] ao lado de cada afirmação factual relevante. "
        "Se houver ambiguidade, apresente a leitura mais segura e explique a dúvida com citação."
    )


def _answer_input(query_results: Mapping[str, Any], grounding: Sequence[Mapping[str, Any]]) -> str:
    filters = dict(query_results.get("filters", {}) or {})
    filter_text = ", ".join(f"{key}={value}" for key, value in filters.items()) if filters else "sem filtros"
    grounding_lines = []
    for item in grounding:
        grounding_lines.extend(
            [
                f"[{item['id']}] {item['reference']}",
                f"arquétipo={item.get('document_archetype') or 'unknown'} | "
                f"score={item.get('score') or 0} | modo={item.get('retrieval_mode') or 'textual'}",
                item.get("text") or "",
                "",
            ]
        )

    return "\n".join(
        [
            f"Pergunta: {query_results.get('query', '')}",
            f"Filtros: {filter_text}",
            f"Modo de retrieval: {query_results.get('mode', 'textual')}",
            f"Perfil de ranking: {query_results.get('ranking_profile', DEFAULT_RANKING_PROFILE)}",
            "",
            "Grounding disponível:",
            *grounding_lines,
            "Responda em português, de forma objetiva, e cite as fontes no formato [n].",
        ]
    )


def _build_markdown(answer_text: str, citations: Sequence[Mapping[str, Any]]) -> str:
    lines = [answer_text.strip()]
    if citations:
        lines.extend(["", "## Fontes usadas", ""])
        for citation in citations:
            lines.append(f"- [{citation.get('id')}] {citation.get('reference')}")
    return "\n".join(lines).strip()


def _extract_citations(answer_text: str, grounding: Sequence[Mapping[str, Any]]) -> list[dict]:
    seen_ids: list[int] = []
    for match in _CITATION_PATTERN.findall(answer_text):
        citation_id = int(match)
        if citation_id not in seen_ids:
            seen_ids.append(citation_id)

    by_id = {int(item.get("id") or 0): dict(item) for item in grounding}
    selected = [by_id[citation_id] for citation_id in seen_ids if citation_id in by_id]
    if selected:
        return [
            {"id": item.get("id"), "reference": item.get("reference")}
            for item in selected
        ]
    return [
        {"id": item.get("id"), "reference": item.get("reference")}
        for item in grounding
    ]


def _create_openai_client(settings: Any) -> Any:
    from openai import OpenAI

    return OpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=_azure_openai_base_url(settings.azure_openai_endpoint or ""),
    )


def generate_answer_payload(
    query_results: Mapping[str, Any],
    *,
    client_factory: Callable[[Any], Any] | None = None,
) -> dict:
    normalized_profile = normalize_ranking_profile(query_results.get("ranking_profile"))
    grounding = build_grounding(query_results)
    base_payload = {
        "artifact_role": "answer_results",
        "query": query_results.get("query"),
        "filters": dict(query_results.get("filters", {}) or {}),
        "mode": query_results.get("mode"),
        "ranking_profile": normalized_profile,
        "provider": "azure_openai",
        "deployment": None,
        "response_id": None,
        "status": "provider_error",
        "answer_text": "",
        "answer_markdown": "",
        "citations": [],
        "grounding": grounding,
    }

    if not grounding:
        message = "Nenhum contexto relevante foi recuperado para responder com grounding."
        return {
            **base_payload,
            "status": "no_context",
            "answer_text": message,
            "answer_markdown": message,
        }

    settings = get_settings()
    base_payload["deployment"] = settings.azure_openai_deployment

    missing = _missing_config_messages(settings)
    if missing:
        return {
            **base_payload,
            "status": "config_error",
            "answer_text": "Configuração ausente para Azure OpenAI: " + ", ".join(missing) + ".",
        }

    try:
        client = client_factory(settings) if client_factory is not None else _create_openai_client(settings)
        response = client.responses.create(
            model=settings.azure_openai_deployment,
            instructions=_answer_instructions(),
            input=_answer_input(query_results, grounding),
        )
        answer_text = str(getattr(response, "output_text", "") or "").strip()
        citations = _extract_citations(answer_text, grounding)
        return {
            **base_payload,
            "deployment": settings.azure_openai_deployment,
            "response_id": getattr(response, "id", None),
            "status": "ok",
            "answer_text": answer_text,
            "answer_markdown": _build_markdown(answer_text, citations),
            "citations": citations,
        }
    except Exception as exc:
        return {
            **base_payload,
            "deployment": settings.azure_openai_deployment,
            "status": "provider_error",
            "answer_text": f"Falha ao gerar resposta com Azure OpenAI: {exc}",
        }
