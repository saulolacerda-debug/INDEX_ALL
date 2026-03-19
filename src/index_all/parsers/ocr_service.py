from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Callable, Literal

from index_all.config import Settings, get_settings


OCRProviderName = Literal["auto", "azure_vision", "rapidocr", "tesseract"]
AUTO_PROVIDER_SEQUENCE: tuple[OCRProviderName, ...] = ("azure_vision", "rapidocr", "tesseract")


class OCRProviderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRLine:
    text: str
    page_number: int
    line_number: int
    confidence: float | None = None
    bounding_box: list[float] | None = None


def _normalize_provider_name(value: str | None) -> OCRProviderName:
    normalized = (value or "auto").strip().lower().replace("-", "_")
    if normalized in {"auto", "azure_vision", "rapidocr", "tesseract"}:
        return normalized  # type: ignore[return-value]
    raise ValueError(f"Unsupported OCR provider: {value}")


def _provider_sequence(settings: Settings) -> tuple[OCRProviderName, ...]:
    provider = _normalize_provider_name(settings.ocr_provider)
    if provider == "auto":
        return AUTO_PROVIDER_SEQUENCE
    return (provider,)


def _flatten_bounding_box(polygon: object) -> list[float] | None:
    if not polygon:
        return None

    flattened: list[float] = []
    for point in list(polygon):
        if isinstance(point, (int, float)):
            flattened.append(float(point))
            continue

        x = getattr(point, "x", None)
        y = getattr(point, "y", None)
        if x is None or y is None:
            continue
        flattened.extend((float(x), float(y)))

    return flattened or None


def _build_payload(
    *,
    provider: OCRProviderName,
    engine: str,
    settings: Settings,
    lines: list[OCRLine],
    details: dict | None = None,
) -> dict:
    confidences = [line.confidence for line in lines if line.confidence is not None]
    page_numbers = {line.page_number for line in lines if line.page_number}
    return {
        "provider": provider,
        "engine": engine,
        "language_hint": settings.ocr_language_hint,
        "line_count": len(lines),
        "page_count": len(page_numbers) or 1,
        "average_confidence": round(mean(confidences), 4) if confidences else None,
        "details": details or {},
        "lines": [
            {
                "text": line.text,
                "page_number": line.page_number,
                "line_number": line.line_number,
                "confidence": line.confidence,
                "bounding_box": line.bounding_box,
            }
            for line in lines
        ],
    }


def _extract_azure_read_lines(result: object) -> list[OCRLine]:
    read_result = getattr(result, "read", None) or result
    extracted: list[OCRLine] = []

    pages = getattr(read_result, "pages", None) or []
    if pages:
        for page_index, page in enumerate(pages, start=1):
            page_number = int(getattr(page, "page_number", page_index) or page_index)
            lines = getattr(page, "lines", None) or []
            for line_index, line in enumerate(lines, start=1):
                text = str(getattr(line, "text", "") or "").strip()
                if not text:
                    continue
                extracted.append(
                    OCRLine(
                        text=text,
                        page_number=page_number,
                        line_number=line_index,
                        confidence=(float(getattr(line, "confidence")) if getattr(line, "confidence", None) is not None else None),
                        bounding_box=_flatten_bounding_box(
                            getattr(line, "bounding_polygon", None) or getattr(line, "polygon", None)
                        ),
                    )
                )
        return extracted

    blocks = getattr(read_result, "blocks", None) or []
    for page_index, block in enumerate(blocks, start=1):
        lines = getattr(block, "lines", None) or []
        for line_index, line in enumerate(lines, start=1):
            text = str(getattr(line, "text", "") or "").strip()
            if not text:
                continue
            extracted.append(
                OCRLine(
                    text=text,
                    page_number=page_index,
                    line_number=line_index,
                    confidence=(float(getattr(line, "confidence")) if getattr(line, "confidence", None) is not None else None),
                    bounding_box=_flatten_bounding_box(
                        getattr(line, "bounding_polygon", None) or getattr(line, "polygon", None)
                    ),
                )
            )

    if extracted:
        return extracted

    content = str(getattr(read_result, "content", "") or "").strip()
    return [
        OCRLine(
            text=line_text.strip(),
            page_number=1,
            line_number=line_index,
        )
        for line_index, line_text in enumerate(content.splitlines(), start=1)
        if line_text.strip()
    ]


def _run_azure_vision_ocr(path: Path, settings: Settings) -> dict:
    if not settings.azure_vision_endpoint or not settings.azure_vision_key:
        raise OCRProviderUnavailable(
            "Azure AI Vision nao configurado. Defina INDEX_ALL_AZURE_VISION_ENDPOINT e INDEX_ALL_AZURE_VISION_KEY."
        )

    try:
        from azure.ai.vision.imageanalysis import ImageAnalysisClient
        from azure.ai.vision.imageanalysis.models import VisualFeatures
        from azure.core.credentials import AzureKeyCredential
    except ImportError as exc:
        raise OCRProviderUnavailable(
            "Pacote azure-ai-vision-imageanalysis nao instalado."
        ) from exc

    client = ImageAnalysisClient(
        endpoint=settings.azure_vision_endpoint,
        credential=AzureKeyCredential(settings.azure_vision_key),
    )
    result = client.analyze(
        image_data=path.read_bytes(),
        visual_features=[VisualFeatures.READ],
        language=_azure_language_hint(settings.ocr_language_hint),
    )
    lines = _extract_azure_read_lines(result)
    return _build_payload(
        provider="azure_vision",
        engine="azure_ai_vision_read",
        settings=settings,
        lines=lines,
        details={"model": "read"},
    )


def _run_rapidocr(path: Path, settings: Settings) -> dict:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise OCRProviderUnavailable("Pacote rapidocr-onnxruntime nao instalado.") from exc

    engine = RapidOCR()
    result, _elapsed = engine(str(path))
    lines: list[OCRLine] = []
    for line_index, item in enumerate(result or [], start=1):
        if not item or len(item) < 2:
            continue
        polygon = item[0]
        text = str(item[1] or "").strip()
        if not text:
            continue
        confidence = float(item[2]) if len(item) > 2 and item[2] is not None else None
        lines.append(
            OCRLine(
                text=text,
                page_number=1,
                line_number=line_index,
                confidence=confidence,
                bounding_box=_flatten_bounding_box(polygon),
            )
        )

    return _build_payload(
        provider="rapidocr",
        engine="rapidocr_onnxruntime",
        settings=settings,
        lines=lines,
    )


def _tesseract_language_hint(language_hint: str) -> str:
    tokens = [token.strip().lower() for token in language_hint.split(",") if token.strip()]
    if not tokens:
        return "por+eng"

    mapping = {
        "pt": "por",
        "pt-br": "por",
        "pt_br": "por",
        "en": "eng",
        "en-us": "eng",
        "en_us": "eng",
    }
    resolved = [mapping.get(token, token) for token in tokens]
    return "+".join(dict.fromkeys(resolved))


def _merge_word_boxes(boxes: list[tuple[int, int, int, int]]) -> list[float] | None:
    if not boxes:
        return None
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return [float(left), float(top), float(right), float(top), float(right), float(bottom), float(left), float(bottom)]


def _azure_language_hint(language_hint: str) -> str | None:
    first_token = next((token.strip().lower() for token in language_hint.split(",") if token.strip()), "")
    if not first_token:
        return None
    if first_token in {"pt-br", "pt_br"}:
        return "pt"
    if first_token in {"en-us", "en_us"}:
        return "en"
    return first_token


def _run_tesseract(path: Path, settings: Settings) -> dict:
    try:
        from PIL import Image
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise OCRProviderUnavailable("Pacotes Pillow/pytesseract nao instalados.") from exc

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    elif shutil.which("tesseract") is None:
        raise OCRProviderUnavailable(
            "Executavel do Tesseract nao encontrado. Defina INDEX_ALL_TESSERACT_CMD ou instale o Tesseract no PATH."
        )

    with Image.open(path) as image:
        data = pytesseract.image_to_data(
            image,
            lang=_tesseract_language_hint(settings.ocr_language_hint),
            output_type=Output.DICT,
        )

    groups: dict[tuple[int, int, int, int], dict] = {}
    item_count = len(data.get("text", []))
    for item_index in range(item_count):
        text = str(data["text"][item_index] or "").strip()
        if not text:
            continue

        page_number = int(data.get("page_num", [1] * item_count)[item_index] or 1)
        block_num = int(data.get("block_num", [0] * item_count)[item_index] or 0)
        par_num = int(data.get("par_num", [0] * item_count)[item_index] or 0)
        line_num = int(data.get("line_num", [item_index + 1] * item_count)[item_index] or (item_index + 1))
        key = (page_number, block_num, par_num, line_num)

        group = groups.setdefault(
            key,
            {
                "page_number": page_number,
                "line_number": line_num,
                "texts": [],
                "confidences": [],
                "boxes": [],
            },
        )
        group["texts"].append(text)
        confidence = data.get("conf", [None] * item_count)[item_index]
        try:
            parsed_confidence = float(confidence)
        except (TypeError, ValueError):
            parsed_confidence = None
        if parsed_confidence is not None and parsed_confidence >= 0:
            group["confidences"].append(parsed_confidence / 100.0 if parsed_confidence > 1 else parsed_confidence)

        left = int(data.get("left", [0] * item_count)[item_index] or 0)
        top = int(data.get("top", [0] * item_count)[item_index] or 0)
        width = int(data.get("width", [0] * item_count)[item_index] or 0)
        height = int(data.get("height", [0] * item_count)[item_index] or 0)
        group["boxes"].append((left, top, width, height))

    lines = [
        OCRLine(
            text=" ".join(group["texts"]),
            page_number=group["page_number"],
            line_number=group["line_number"],
            confidence=(round(mean(group["confidences"]), 4) if group["confidences"] else None),
            bounding_box=_merge_word_boxes(group["boxes"]),
        )
        for _key, group in sorted(groups.items())
    ]

    return _build_payload(
        provider="tesseract",
        engine="pytesseract",
        settings=settings,
        lines=lines,
    )


PROVIDER_RUNNERS: dict[OCRProviderName, Callable[[Path, Settings], dict]] = {
    "azure_vision": _run_azure_vision_ocr,
    "rapidocr": _run_rapidocr,
    "tesseract": _run_tesseract,
}


def extract_image_ocr(path: Path, *, settings: Settings | None = None) -> dict:
    resolved_settings = settings or get_settings()
    attempts: list[str] = []
    sequence = _provider_sequence(resolved_settings)

    for provider in sequence:
        runner = PROVIDER_RUNNERS[provider]
        try:
            payload = runner(path, resolved_settings)
            payload["attempted_providers"] = list(sequence[: sequence.index(provider) + 1])
            return payload
        except OCRProviderUnavailable as exc:
            attempts.append(f"{provider}: {exc}")
            continue
        except Exception as exc:
            if _normalize_provider_name(resolved_settings.ocr_provider) != "auto":
                raise RuntimeError(f"OCR via {provider} falhou para {path.name}: {exc}") from exc
            attempts.append(f"{provider}: {exc}")

    raise RuntimeError(
        "Nenhum provedor OCR disponivel para leitura de imagens. "
        "Configure Azure AI Vision ou instale rapidocr-onnxruntime, ou Pillow+pytesseract+Tesseract. "
        f"Tentativas: {' | '.join(attempts) if attempts else 'nenhuma'}"
    )
