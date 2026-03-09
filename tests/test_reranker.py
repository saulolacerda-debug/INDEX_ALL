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
