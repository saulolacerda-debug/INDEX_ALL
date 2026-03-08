from __future__ import annotations

from datetime import datetime
from pathlib import Path


def extract_common_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "file_name": path.name,
        "file_stem": path.stem,
        "file_type": path.suffix.lower().lstrip("."),
        "file_size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "source_path": str(path),
    }
