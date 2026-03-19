from __future__ import annotations

import json
from pathlib import Path

from index_all.config import Settings
from index_all.ingestion.file_router import get_parser_for_path
from index_all.main import process_file
from index_all.parsers import image_parser, ocr_service

from tests.helpers import create_png_stub, workspace_test_dir


def test_file_router_supports_common_image_extensions():
    parser = get_parser_for_path(Path("captura.PNG"))

    assert parser is image_parser.parse_image


def test_image_parser_processes_png_with_mocked_ocr_end_to_end(monkeypatch):
    fake_ocr_payload = {
        "provider": "mock_ocr",
        "engine": "mock_engine",
        "language_hint": "pt,en",
        "page_count": 1,
        "average_confidence": 0.982,
        "attempted_providers": ["rapidocr"],
        "lines": [
            {
                "text": "MANUAL OPERACIONAL DE APURAÇÃO",
                "page_number": 1,
                "line_number": 1,
                "confidence": 0.99,
                "bounding_box": [0, 0, 10, 0, 10, 10, 0, 10],
            },
            {
                "text": "Etapa 1 - Receber arquivo",
                "page_number": 1,
                "line_number": 2,
                "confidence": 0.974,
                "bounding_box": [0, 12, 40, 12, 40, 24, 0, 24],
            },
            {
                "text": "Clique no botão Enviar",
                "page_number": 1,
                "line_number": 3,
                "confidence": 0.982,
                "bounding_box": [0, 26, 60, 26, 60, 38, 0, 38],
            },
        ],
    }
    monkeypatch.setattr(image_parser, "extract_image_ocr", lambda _path: fake_ocr_payload)

    with workspace_test_dir() as temp_root:
        image_path = create_png_stub(temp_root / "manual.png")

        output_dir = process_file(image_path, temp_root / "saida")

        content_payload = json.loads((output_dir / "content.json").read_text(encoding="utf-8"))

        assert content_payload["metadata"]["file_name"] == "manual.png"
        assert content_payload["document_archetype"] == "manual_procedural"
        assert content_payload["document_profile"]["primary_structure"] == "ocr_image"
        assert content_payload["parser_metadata"]["ocr_provider"] == "mock_ocr"
        assert content_payload["parser_metadata"]["ocr_engine"] == "mock_engine"
        assert content_payload["parser_metadata"]["ocr_line_count"] == 3
        assert content_payload["blocks"][0]["text"] == "MANUAL OPERACIONAL DE APURAÇÃO"
        assert content_payload["blocks"][0]["locator"]["page"] == 1
        assert content_payload["blocks"][0]["extra"]["bounding_box"]


def test_extract_image_ocr_falls_back_to_next_provider(monkeypatch):
    calls: list[str] = []

    def azure_runner(_path, _settings):
        calls.append("azure_vision")
        raise ocr_service.OCRProviderUnavailable("nao configurado")

    def rapid_runner(_path, settings):
        calls.append("rapidocr")
        return {
            "provider": "rapidocr",
            "engine": "rapidocr_onnxruntime",
            "language_hint": settings.ocr_language_hint,
            "page_count": 1,
            "average_confidence": 0.91,
            "details": {},
            "lines": [
                {
                    "text": "OCR local ativo",
                    "page_number": 1,
                    "line_number": 1,
                    "confidence": 0.91,
                    "bounding_box": None,
                }
            ],
        }

    monkeypatch.setitem(ocr_service.PROVIDER_RUNNERS, "azure_vision", azure_runner)
    monkeypatch.setitem(ocr_service.PROVIDER_RUNNERS, "rapidocr", rapid_runner)

    settings = Settings(
        project_root=Path("."),
        data_dir=Path("data"),
        raw_dir=Path("data/raw"),
        processed_dir=Path("data/processed"),
        samples_dir=Path("data/samples"),
        ocr_provider="auto",
        ocr_language_hint="pt,en",
        azure_vision_endpoint=None,
        azure_vision_key=None,
        tesseract_cmd=None,
    )

    with workspace_test_dir() as temp_root:
        image_path = create_png_stub(temp_root / "ocr.png")
        payload = ocr_service.extract_image_ocr(image_path, settings=settings)

    assert payload["provider"] == "rapidocr"
    assert payload["attempted_providers"] == ["azure_vision", "rapidocr"]
    assert calls == ["azure_vision", "rapidocr"]
