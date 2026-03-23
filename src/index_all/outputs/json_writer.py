from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


COMPACT_JSON_FILE_NAMES = {
    "ai_context.json",
    "answer_results.json",
    "catalog.json",
    "collection_metadata.json",
    "content.json",
    "chunks.json",
    "embeddings_index.json",
    "index.json",
    "master_index.json",
    "retrieval_preview.json",
    "search_index.json",
}


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = path.name in COMPACT_JSON_FILE_NAMES
    json_text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=None if compact else 2,
        separators=(",", ":") if compact else None,
    )
    path.write_text(
        json_text + "\n",
        encoding="utf-8",
    )


def write_json_bundle(base_dir: Path, payloads: Mapping[str, dict | list]) -> None:
    for file_name, payload in payloads.items():
        write_json(base_dir / file_name, payload)
