from __future__ import annotations

from index_all.config import get_settings


def test_settings_load_index_all_azure_openai_variables(monkeypatch):
    monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_ENDPOINT", "https://demo.openai.azure.com/")
    monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

    settings = get_settings()

    assert settings.azure_openai_endpoint == "https://demo.openai.azure.com/"
    assert settings.azure_openai_api_key == "test-key"
    assert settings.azure_openai_deployment == "gpt-4.1-mini"


def test_settings_fallback_to_generic_azure_openai_variables(monkeypatch):
    monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fallback.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fallback-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-nano")

    settings = get_settings()

    assert settings.azure_openai_endpoint == "https://fallback.openai.azure.com/"
    assert settings.azure_openai_api_key == "fallback-key"
    assert settings.azure_openai_deployment == "gpt-4.1-nano"
