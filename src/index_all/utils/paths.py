from __future__ import annotations

import re
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    sanitized = sanitized.strip("._")
    return sanitized or "item"


def unique_output_dir(base_dir: Path, file_stem: str) -> Path:
    stem = sanitize_name(file_stem)
    candidate = base_dir / stem
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    counter = 2
    while True:
        candidate = base_dir / f"{stem}_{counter}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        counter += 1
