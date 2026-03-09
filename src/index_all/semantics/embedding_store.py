from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


class LocalEmbeddingStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {
                "artifact_role": "local_embedding_store",
                "chunk_count": 0,
                "metadata": {
                    "embedding_count": 0,
                    "document_archetype_counts": {},
                },
                "records": [],
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def load_chunks(self) -> list[dict]:
        payload = self.load()
        return list(payload.get("records", []) or [])

    def save_chunks(self, chunks: Sequence[dict]) -> dict:
        records = []
        for chunk in chunks:
            record = dict(chunk)
            record.setdefault("embedding", None)
            records.append(record)

        archetype_counts = Counter(str(record.get("document_archetype") or "unknown") for record in records)
        embedding_count = sum(1 for record in records if record.get("embedding") is not None)
        payload = {
            "artifact_role": "local_embedding_store",
            "chunk_count": len(records),
            "metadata": {
                "embedding_count": embedding_count,
                "document_archetype_counts": dict(sorted(archetype_counts.items())),
            },
            "records": records,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def upsert_embeddings(self, embeddings_by_chunk_id: Mapping[str, Sequence[float] | None]) -> dict:
        payload = self.load()
        records = list(payload.get("records", []) or [])
        updated = 0

        for record in records:
            chunk_id = str(record.get("chunk_id") or "")
            if chunk_id not in embeddings_by_chunk_id:
                continue
            embedding = embeddings_by_chunk_id[chunk_id]
            record["embedding"] = list(embedding) if embedding is not None else None
            updated += 1

        payload["records"] = records
        payload["chunk_count"] = len(records)
        payload["updated_embeddings"] = updated
        payload["metadata"] = {
            "embedding_count": sum(1 for record in records if record.get("embedding") is not None),
            "document_archetype_counts": dict(
                sorted(Counter(str(record.get("document_archetype") or "unknown") for record in records).items())
            ),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
