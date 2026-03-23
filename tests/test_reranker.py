from __future__ import annotations

from index_all.semantics.reranker import rerank_candidates


def test_reranker_promotes_heading_match_and_vector_signal():
    candidates = [
        {
            "chunk_id": "chunk_heading",
            "file_name": "manual.docx",
            "document_archetype": "manual_procedural",
            "source_kind": "chunk",
            "heading_path_text": "Manual > Integridade do arquivo",
            "text": "Verificar o arquivo recebido.",
            "text_score": 18,
            "vector_score": 0.42,
            "has_embedding": True,
            "text_length": 92,
        },
        {
            "chunk_id": "chunk_body_only",
            "file_name": "manual.docx",
            "document_archetype": "manual_procedural",
            "source_kind": "chunk",
            "heading_path_text": "Manual > Procedimento",
            "text": "A palavra integridade aparece apenas no corpo do texto.",
            "text_score": 18,
            "vector_score": 0.18,
            "has_embedding": True,
            "text_length": 92,
        },
    ]

    reranked = rerank_candidates("integridade", candidates, limit=2)

    assert [item["chunk_id"] for item in reranked] == ["chunk_heading", "chunk_body_only"]
    assert reranked[0]["score_breakdown"]["heading"] > reranked[1]["score_breakdown"]["heading"]
    assert reranked[0]["score_breakdown"]["vector"] > reranked[1]["score_breakdown"]["vector"]
    assert reranked[0]["retrieval_mode"] == "hybrid"


def test_reranker_boosts_exact_legal_reference_and_penalizes_partial_match():
    candidates = [
        {
            "chunk_id": "chunk_156",
            "file_name": "norma.pdf",
            "document_archetype": "legislation_normative",
            "source_kind": "chunk",
            "heading_path_text": "Título I > Art. 156 - Regras gerais do IBS",
            "text": "Art. 156 trata de disposições gerais do IBS.",
            "text_score": 60,
            "vector_score": 0.25,
            "has_embedding": True,
            "text_length": 120,
        },
        {
            "chunk_id": "chunk_156a",
            "file_name": "norma.pdf",
            "document_archetype": "legislation_normative",
            "source_kind": "chunk",
            "heading_path_text": "Título I > Art. 156-A - Imposto sobre Bens e Serviços (IBS)",
            "text": "Art. 156-A institui o IBS.",
            "text_score": 58,
            "vector_score": 0.22,
            "has_embedding": True,
            "text_length": 120,
        },
    ]

    reranked = rerank_candidates("art. 156-a ibs", candidates, limit=2)

    assert [item["chunk_id"] for item in reranked] == ["chunk_156a", "chunk_156"]
    assert reranked[0]["score_breakdown"]["legal_reference"] > 0
    assert reranked[1]["score_breakdown"]["legal_reference"] == 0


def test_reranker_generic_profile_disables_legal_reference_weight():
    candidates = [
        {
            "chunk_id": "chunk_156a",
            "source_kind": "chunk",
            "file_name": "norma.pdf",
            "document_archetype": "legislation_normative",
            "heading_path_text": "Titulo I > Art. 156-A - IBS",
            "text": "Art. 156-A institui o IBS.",
            "text_score": 24.0,
            "vector_score": 0.71,
            "has_embedding": True,
        },
        {
            "chunk_id": "chunk_156",
            "source_kind": "chunk",
            "file_name": "norma.pdf",
            "document_archetype": "legislation_normative",
            "heading_path_text": "Titulo I > Art. 156 - Regras gerais",
            "text": "Art. 156 trata de disposicoes gerais do IBS.",
            "text_score": 20.0,
            "vector_score": 0.52,
            "has_embedding": True,
        },
    ]

    reranked = rerank_candidates("art. 156-a ibs", candidates, limit=2, ranking_profile="generic")

    assert all(item["ranking_profile"] == "generic" for item in reranked)
    assert all(item["score_breakdown"]["legal_reference"] == 0 for item in reranked)
