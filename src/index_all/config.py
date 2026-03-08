from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path
    samples_dir: Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_settings() -> Settings:
    project_root = get_project_root()
    data_dir = project_root / "data"
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        raw_dir=data_dir / "raw",
        processed_dir=data_dir / "processed",
        samples_dir=data_dir / "samples",
    )
