from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position
from index_all.outputs.json_writer import read_json, write_json
from index_all.semantics.search_engine import normalize_text, query_tokens

DEFAULT_VECTOR_SIZE = 192
DEFAULT_EMBEDDING_ALGORITHM = "local_hash_embedding_v1"


def _stable_hash(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _safe_float_list(values: Sequence[float] | None) -> list[float] | None:
    if not values:
        return None
    return [round(float(value), 6) for value in values]


def _l2_normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0:
        return vector
    return [value / magnitude for value in vector]


def _heading_path_text(chunk: Mapping[str, Any]) -> str:
    explicit = str(chunk.get("heading_path_text") or "").strip()
    if explicit:
        return explicit
    heading_path = [str(part).strip() for part in (chunk.get("heading_path") or []) if str(part).strip()]
    if heading_path:
        return " > ".join(heading_path)
    return str(chunk.get("heading") or "").strip()


def _locator_payload(chunk: Mapping[str, Any]) -> dict:
    return dict(chunk.get("locator", {}) or {})


def _locator_text(chunk: Mapping[str, Any]) -> str:
    locator = _locator_payload(chunk)
    return str(chunk.get("locator_path") or format_locator_path(locator) or format_position(locator) or "").strip()


def _chunk_context_text(chunk: Mapping[str, Any]) -> str:
    heading = _heading_path_text(chunk)
    body = " ".join(str(chunk.get("text") or "").split()).strip()
    parts = [
        heading,
        heading,
        str(chunk.get("heading") or "").strip(),
        str(chunk.get("file_name") or "").strip(),
        str(chunk.get("document_archetype") or "").replace("_", " ").strip(),
        _locator_text(chunk),
        body,
    ]
    return " | ".join(part for part in parts if part)


def _chunk_fingerprint(chunk: Mapping[str, Any]) -> str:
    text = normalize_text(_chunk_context_text(chunk))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def build_local_embedding(
    text: str,
    *,
    vector_size: int = DEFAULT_VECTOR_SIZE,
) -> list[float] | None:
    normalized = normalize_text(text)
    tokens = query_tokens(normalized)
    if not tokens:
        return None

    vector = [0.0] * max(int(vector_size), 32)

    def add_feature(feature: str, weight: float) -> None:
        primary = _stable_hash(f"primary::{feature}") % len(vector)
        secondary = _stable_hash(f"secondary::{feature}") % len(vector)
        sign = 1.0 if _stable_hash(f"sign::{feature}") % 2 == 0 else -1.0
        vector[primary] += weight * sign
        vector[secondary] += weight * 0.45 * sign

    for token in tokens:
        token_weight = 1.0 + min(len(token), 12) / 24
        add_feature(f"word::{token}", token_weight)
        if len(token) >= 4:
            add_feature(f"prefix::{token[:4]}", 0.28)
            add_feature(f"suffix::{token[-4:]}", 0.28)

    for left, right in zip(tokens, tokens[1:]):
        add_feature(f"bigram::{left}_{right}", 1.35)

    condensed = normalized.replace(" ", "_")
    for size, weight in ((3, 0.18), (4, 0.12)):
        if len(condensed) < size:
            continue
        for index in range(len(condensed) - size + 1):
            add_feature(f"char::{condensed[index:index + size]}", weight)

    return _safe_float_list(_l2_normalize(vector))


def cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size <= 0:
        return 0.0
    score = sum(float(left[index]) * float(right[index]) for index in range(size))
    return round(max(min(score, 1.0), -1.0), 6)


class LocalEmbeddingStore:
    def __init__(
        self,
        path: Path,
        *,
        vector_size: int = DEFAULT_VECTOR_SIZE,
        algorithm: str = DEFAULT_EMBEDDING_ALGORITHM,
    ):
        if path.suffix.lower() == ".json":
            self.collection_dir = path.parent
            self.chunks_path = path.parent / "chunks.json"
            self.embeddings_path = path.parent / "embeddings_index.json"
            if path.name == "chunks.json":
                self.chunks_path = path
            elif path.name == "embeddings_index.json":
                self.embeddings_path = path
        else:
            self.collection_dir = path
            self.chunks_path = path / "chunks.json"
            self.embeddings_path = path / "embeddings_index.json"

        self.vector_size = int(vector_size)
        self.algorithm = str(algorithm)

    def _default_chunks_payload(self) -> dict:
        return {
            "artifact_role": "local_embedding_store",
            "chunk_count": 0,
            "metadata": {
                "embedding_count": 0,
                "embedding_coverage": 0.0,
                "vector_size": self.vector_size,
                "embedding_algorithm": self.algorithm,
                "document_archetype_counts": {},
            },
            "records": [],
        }

    def _default_embeddings_payload(self) -> dict:
        return {
            "artifact_role": "local_embeddings_index",
            "chunk_count": 0,
            "metadata": {
                "embedding_count": 0,
                "embedding_coverage": 0.0,
                "vector_size": self.vector_size,
                "embedding_algorithm": self.algorithm,
                "built_count": 0,
                "reused_count": 0,
                "document_archetype_counts": {},
            },
            "records": [],
        }

    def load(self) -> dict:
        return self.load_chunks_payload()

    def load_chunks_payload(self) -> dict:
        if not self.chunks_path.exists():
            return self._default_chunks_payload()
        return read_json(self.chunks_path)

    def load_chunks(self) -> list[dict]:
        payload = self.load_chunks_payload()
        return list(payload.get("records", []) or [])

    def load_embeddings_payload(self) -> dict:
        if not self.embeddings_path.exists():
            return self._default_embeddings_payload()
        payload = read_json(self.embeddings_path)
        metadata = dict(payload.get("metadata", {}) or {})
        metadata.setdefault("vector_size", self.vector_size)
        metadata.setdefault("embedding_algorithm", self.algorithm)
        payload["metadata"] = metadata
        return payload

    def load_embeddings(self) -> dict[str, list[float] | None]:
        payload = self.load_embeddings_payload()
        return {
            str(record.get("chunk_id") or ""): _safe_float_list(record.get("vector"))
            for record in (payload.get("records", []) or [])
            if record.get("chunk_id")
        }

    def has_embeddings(self) -> bool:
        return int((self.load_embeddings_payload().get("metadata", {}) or {}).get("embedding_count", 0)) > 0

    def embed_query(self, query: str) -> list[float] | None:
        return build_local_embedding(query, vector_size=self.vector_size)

    def embed_chunk(self, chunk: Mapping[str, Any]) -> list[float] | None:
        return build_local_embedding(_chunk_context_text(chunk), vector_size=self.vector_size)

    def _chunk_stats(self, records: Sequence[Mapping[str, Any]]) -> dict:
        archetype_counts = Counter(str(record.get("document_archetype") or "unknown") for record in records)
        embedding_count = sum(1 for record in records if record.get("embedding") is not None)
        chunk_count = len(records)
        return {
            "embedding_count": embedding_count,
            "embedding_coverage": round((embedding_count / chunk_count), 4) if chunk_count else 0.0,
            "vector_size": self.vector_size,
            "embedding_algorithm": self.algorithm,
            "document_archetype_counts": dict(sorted(archetype_counts.items())),
        }

    def _embedding_stats(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        built_count: int = 0,
        reused_count: int = 0,
    ) -> dict:
        archetype_counts = Counter(str(record.get("document_archetype") or "unknown") for record in records)
        embedding_count = sum(1 for record in records if record.get("vector") is not None)
        chunk_count = len(records)
        return {
            "embedding_count": embedding_count,
            "embedding_coverage": round((embedding_count / chunk_count), 4) if chunk_count else 0.0,
            "vector_size": self.vector_size,
            "embedding_algorithm": self.algorithm,
            "built_count": built_count,
            "reused_count": reused_count,
            "document_archetype_counts": dict(sorted(archetype_counts.items())),
        }

    def _embedding_record_for_chunk(
        self,
        chunk: Mapping[str, Any],
        *,
        vector: Sequence[float] | None,
        text_fingerprint: str | None = None,
    ) -> dict:
        return {
            "chunk_id": chunk.get("chunk_id"),
            "file_name": chunk.get("file_name"),
            "file_type": chunk.get("file_type"),
            "document_archetype": chunk.get("document_archetype"),
            "heading_path_text": _heading_path_text(chunk),
            "locator": _locator_payload(chunk),
            "locator_path": _locator_text(chunk) or None,
            "source_kind": chunk.get("source_kind") or "chunk",
            "text_fingerprint": text_fingerprint or _chunk_fingerprint(chunk),
            "vector": _safe_float_list(vector),
        }

    def hydrate_chunks(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        embedding_payload: Mapping[str, Any] | None = None,
    ) -> list[dict]:
        payload = embedding_payload or self.load_embeddings_payload()
        embeddings_by_chunk_id = {
            str(record.get("chunk_id") or ""): _safe_float_list(record.get("vector"))
            for record in (payload.get("records", []) or [])
            if record.get("chunk_id")
        }

        records: list[dict] = []
        for chunk in chunks:
            record = dict(chunk)
            record.setdefault("source_kind", "chunk")
            record["heading_path_text"] = _heading_path_text(record)
            record["locator"] = _locator_payload(record)
            record["locator_path"] = _locator_text(record) or None
            record["embedding"] = embeddings_by_chunk_id.get(str(record.get("chunk_id") or "")) or None
            record["has_embedding"] = record["embedding"] is not None
            record.setdefault("metadata", {})
            record["metadata"] = dict(record.get("metadata", {}) or {})
            record["metadata"].setdefault("text_length", len(" ".join(str(record.get("text") or "").split())))
            records.append(record)
        return records

    def save_chunks(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        embedding_payload: Mapping[str, Any] | None = None,
    ) -> dict:
        records = self.hydrate_chunks(chunks, embedding_payload=embedding_payload)
        payload = {
            "artifact_role": "local_embedding_store",
            "chunk_count": len(records),
            "metadata": self._chunk_stats(records),
            "records": records,
        }
        write_json(self.chunks_path, payload)
        return payload

    def build_embeddings(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        force: bool = False,
    ) -> dict:
        existing_payload = self.load_embeddings_payload()
        existing_by_chunk_id = {
            str(record.get("chunk_id") or ""): dict(record)
            for record in (existing_payload.get("records", []) or [])
            if record.get("chunk_id")
        }

        built_count = 0
        reused_count = 0
        records: list[dict] = []

        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id") or "")
            text_fingerprint = _chunk_fingerprint(chunk)
            existing = existing_by_chunk_id.get(chunk_id)

            vector: list[float] | None
            if (
                not force
                and existing
                and existing.get("text_fingerprint") == text_fingerprint
                and isinstance(existing.get("vector"), list)
                and existing.get("vector")
            ):
                vector = _safe_float_list(existing.get("vector"))
                reused_count += 1
            else:
                vector = self.embed_chunk(chunk)
                if vector is not None:
                    built_count += 1

            records.append(
                self._embedding_record_for_chunk(
                    chunk,
                    vector=vector,
                    text_fingerprint=text_fingerprint,
                )
            )

        payload = {
            "artifact_role": "local_embeddings_index",
            "chunk_count": len(records),
            "metadata": self._embedding_stats(records, built_count=built_count, reused_count=reused_count),
            "records": records,
        }
        write_json(self.embeddings_path, payload)
        if self.chunks_path.exists():
            self.save_chunks(self.load_chunks(), embedding_payload=payload)
        return payload

    def upsert_embeddings(self, embeddings_by_chunk_id: Mapping[str, Sequence[float] | None]) -> dict:
        chunks_by_chunk_id = {
            str(chunk.get("chunk_id") or ""): chunk
            for chunk in self.load_chunks()
            if chunk.get("chunk_id")
        }
        payload = self.load_embeddings_payload()
        records_by_chunk_id = {
            str(record.get("chunk_id") or ""): dict(record)
            for record in (payload.get("records", []) or [])
            if record.get("chunk_id")
        }

        updated = 0
        for chunk_id, values in embeddings_by_chunk_id.items():
            chunk = chunks_by_chunk_id.get(str(chunk_id), {"chunk_id": chunk_id})
            record = self._embedding_record_for_chunk(
                chunk,
                vector=values,
                text_fingerprint=_chunk_fingerprint(chunk) if chunk else None,
            )
            records_by_chunk_id[str(chunk_id)] = record
            updated += 1

        records = list(records_by_chunk_id.values())
        payload = {
            "artifact_role": "local_embeddings_index",
            "chunk_count": len(records),
            "updated_embeddings": updated,
            "metadata": self._embedding_stats(records, built_count=updated, reused_count=0),
            "records": records,
        }
        write_json(self.embeddings_path, payload)
        if chunks_by_chunk_id:
            self.save_chunks(list(chunks_by_chunk_id.values()), embedding_payload=payload)
        return payload
