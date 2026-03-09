from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_json_bundle(base_dir: Path, payloads: Mapping[str, dict | list]) -> None:
    for file_name, payload in payloads.items():
        write_json(base_dir / file_name, payload)
