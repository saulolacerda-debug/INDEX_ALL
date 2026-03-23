from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path
    samples_dir: Path
    ocr_provider: str
    ocr_language_hint: str
    azure_vision_endpoint: str | None
    azure_vision_key: str | None
    tesseract_cmd: str | None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_project_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        env_key = key.strip()
        if not env_key or env_key in os.environ:
            continue

        env_value = value.strip()
        if len(env_value) >= 2 and env_value[0] == env_value[-1] and env_value[0] in {'"', "'"}:
            env_value = env_value[1:-1]
        os.environ[env_key] = env_value


def get_settings() -> Settings:
    project_root = get_project_root()
    _load_project_env(project_root)
    data_dir = project_root / "data"
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        raw_dir=data_dir / "raw",
        processed_dir=data_dir / "processed",
        samples_dir=data_dir / "samples",
        ocr_provider=os.getenv("INDEX_ALL_OCR_PROVIDER", "auto").strip() or "auto",
        ocr_language_hint=os.getenv("INDEX_ALL_OCR_LANGUAGE", "pt,en").strip() or "pt,en",
        azure_vision_endpoint=(
            os.getenv("INDEX_ALL_AZURE_VISION_ENDPOINT")
            or os.getenv("AZURE_AI_VISION_ENDPOINT")
            or os.getenv("AZURE_VISION_ENDPOINT")
        ),
        azure_vision_key=(
            os.getenv("INDEX_ALL_AZURE_VISION_KEY")
            or os.getenv("AZURE_AI_VISION_KEY")
            or os.getenv("AZURE_VISION_KEY")
        ),
        tesseract_cmd=os.getenv("INDEX_ALL_TESSERACT_CMD"),
        azure_openai_endpoint=(
            os.getenv("INDEX_ALL_AZURE_OPENAI_ENDPOINT")
            or os.getenv("AZURE_OPENAI_ENDPOINT")
        ),
        azure_openai_api_key=(
            os.getenv("INDEX_ALL_AZURE_OPENAI_API_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
        ),
        azure_openai_deployment=(
            os.getenv("INDEX_ALL_AZURE_OPENAI_DEPLOYMENT")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        ),
    )
