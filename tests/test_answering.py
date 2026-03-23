from __future__ import annotations

import json

from index_all.main import iter_supported_files, process_collection, process_file
from index_all.semantics.query_interface import answer_collection

from tests.helpers import create_legal_docx, create_manual_docx, workspace_test_dir


class _FakeResponse:
    def __init__(self, *, response_id: str, output_text: str) -> None:
        self.id = response_id
        self.output_text = output_text


class _FakeResponsesAPI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(
            response_id="resp_fake_123",
            output_text="A regra de legalidade aparece no dispositivo principal do documento [1].",
        )


class _FakeClient:
    def __init__(self) -> None:
        self.responses = _FakeResponsesAPI()


def test_answer_collection_writes_answer_artifacts_and_updates_collection_metadata(monkeypatch):
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        fake_client = _FakeClient()
        monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_ENDPOINT", "https://demo.openai.azure.com/")
        monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

        result = answer_collection(
            collection_dir,
            "legalidade",
            filters={"document_archetype": "legislation_normative"},
            limit=3,
            ranking_profile="generic",
            write_results_file=True,
            client_factory=lambda settings: fake_client,
        )

        query_results = json.loads((collection_dir / "query_results.json").read_text(encoding="utf-8"))
        answer_results = json.loads((collection_dir / "answer_results.json").read_text(encoding="utf-8"))
        retrieval_preview = json.loads((collection_dir / "retrieval_preview.json").read_text(encoding="utf-8"))
        collection_metadata = json.loads((collection_dir / "collection_metadata.json").read_text(encoding="utf-8"))
        answer_markdown = (collection_dir / "answer_results.md").read_text(encoding="utf-8")

        assert result["status"] == "ok"
        assert result["response_id"] == "resp_fake_123"
        assert query_results["ranking_profile"] == "generic"
        assert answer_results["ranking_profile"] == "generic"
        assert retrieval_preview["ranking_profile"] == "generic"
        assert collection_metadata["available_artifacts"]["answer_results"] == "answer_results.json"
        assert collection_metadata["available_artifacts"]["answer_results_markdown"] == "answer_results.md"
        assert collection_metadata["semantic"]["answer_results"]["status"] == "ok"
        assert "[1]" in answer_markdown
        assert fake_client.responses.calls
        assert fake_client.responses.calls[0]["model"] == "gpt-4.1-mini"
        assert fake_client.responses.calls[0]["instructions"]


def test_answer_collection_returns_no_context_without_calling_model():
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_manual_docx(source_dir / "manual.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        result = answer_collection(
            collection_dir,
            "zzqxv nvrst grounding inexistivel",
            filters={"file_name": "arquivo_inexistente.txt"},
            limit=3,
            write_results_file=True,
            client_factory=lambda settings: (_ for _ in ()).throw(AssertionError("Nao deveria chamar o provider")),
        )

        answer_results = json.loads((collection_dir / "answer_results.json").read_text(encoding="utf-8"))

        assert result["status"] == "no_context"
        assert answer_results["status"] == "no_context"
        assert answer_results["grounding"] == []


def test_answer_collection_reports_config_error_without_partial_markdown(monkeypatch):
    with workspace_test_dir() as temp_root:
        source_dir = temp_root / "entrada"
        source_dir.mkdir()
        create_legal_docx(source_dir / "norma.docx")

        output_root = temp_root / "saida"
        processed_output_dirs = [process_file(path, output_root) for path in iter_supported_files(source_dir)]
        collection_dir = process_collection(source_dir, output_root, processed_output_dirs, build_embeddings=True)

        monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

        result = answer_collection(
            collection_dir,
            "legalidade",
            limit=3,
            write_results_file=True,
        )

        answer_markdown = (collection_dir / "answer_results.md").read_text(encoding="utf-8")

        assert result["status"] == "config_error"
        assert "INDEX_ALL_AZURE_OPENAI_ENDPOINT" in result["answer_text"]
        assert result["answer_markdown"] == ""
        assert "## Resposta" not in answer_markdown
        assert "## Diagnóstico" in answer_markdown
