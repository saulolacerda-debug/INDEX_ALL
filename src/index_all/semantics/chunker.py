from __future__ import annotations

from typing import Sequence

from index_all.indexing.consultation_payload import format_locator_path, format_position
from index_all.indexing.document_classifier import DocumentArchetype


def _entry_block_position(entry_id: str | None) -> int | None:
    if not entry_id:
        return None
    try:
        return int(str(entry_id).split("_")[-1])
    except ValueError:
        return None


def _iter_entries(
    entries: Sequence[dict],
    *,
    path: list[str] | None = None,
    ancestors: list[dict] | None = None,
):
    current_path = list(path or [])
    current_ancestors = list(ancestors or [])

    for entry in entries:
        entry_path = current_path + [str(entry.get("title") or "Sem título")]
        yield {
            "entry": entry,
            "path": entry_path,
            "ancestors": current_ancestors,
        }
        yield from _iter_entries(
            entry.get("children") or [],
            path=entry_path,
            ancestors=current_ancestors + [entry],
        )


def _descendant_block_positions(entry: dict) -> list[int]:
    positions: list[int] = []
    position = _entry_block_position(entry.get("id"))
    if position is not None:
        positions.append(position)
    for child in entry.get("children") or []:
        positions.extend(_descendant_block_positions(child))
    return sorted(set(positions))


def _heading_span_positions(root_entry: dict, block_by_position: dict[int, dict]) -> list[int]:
    root_position = _entry_block_position(root_entry.get("id"))
    if root_position is None:
        return []

    root_level = root_entry.get("level")
    if not isinstance(root_level, int):
        root_level = 1

    positions: list[int] = []
    max_position = max(block_by_position) if block_by_position else root_position
    for position in range(root_position, max_position + 1):
        block = block_by_position.get(position)
        if not block:
            continue

        if position > root_position and block.get("kind") == "heading":
            next_level = (block.get("extra", {}) or {}).get("heading_level")
            if isinstance(next_level, int) and next_level <= root_level:
                break

        positions.append(position)

    return positions


def _collect_chunk_text(block_by_position: dict[int, dict], positions: Sequence[int]) -> tuple[str, list[dict]]:
    texts: list[str] = []
    blocks: list[dict] = []

    for position in sorted(set(int(pos) for pos in positions)):
        block = block_by_position.get(position)
        if not block:
            continue
        text = str(block.get("text") or "").strip()
        if text:
            texts.append(text)
        blocks.append(block)

    return "\n\n".join(texts).strip(), blocks


def _resolved_heading_path_text(heading_path: Sequence[str], fallback_title: str | None = None) -> str:
    normalized = [str(part).strip() for part in heading_path if str(part).strip()]
    if normalized:
        return " > ".join(normalized)
    return str(fallback_title or "").strip()


def _resolved_locator_path(locator: dict, heading_path: Sequence[str], fallback_title: str | None = None) -> str | None:
    locator_path = format_locator_path(locator)
    if locator_path:
        return locator_path
    position_text = format_position(locator)
    if position_text:
        return position_text
    heading_path_text = _resolved_heading_path_text(heading_path, fallback_title=fallback_title)
    return heading_path_text or None


def _first_available_locator(entry: dict, blocks: Sequence[dict]) -> dict:
    locator = dict(entry.get("locator", {}) or {})
    if any(locator.values()):
        return locator
    for block in blocks:
        block_locator = dict(block.get("locator", {}) or {})
        if any(block_locator.values()):
            return block_locator
    return locator


def _chunk_record(
    *,
    chunk_index: int,
    processed_document: dict,
    root_entry: dict,
    heading_path: list[str],
    positions: Sequence[int],
    root_context: dict | None = None,
) -> dict | None:
    metadata = dict(processed_document.get("metadata", {}) or {})
    content = dict(processed_document.get("content", {}) or {})
    blocks = list(content.get("blocks", []) or [])
    block_by_position = {index: block for index, block in enumerate(blocks, start=1)}
    text, chunk_blocks = _collect_chunk_text(block_by_position, positions)
    if not text:
        return None

    locator = _first_available_locator(root_entry, chunk_blocks)
    archetype = content.get("document_archetype") or metadata.get("document_archetype") or "generic_document"
    heading_path_text = _resolved_heading_path_text(heading_path, fallback_title=root_entry.get("title"))
    locator_path = _resolved_locator_path(locator, heading_path, fallback_title=root_entry.get("title"))

    chunk = {
        "chunk_id": f"chunk_{chunk_index:05d}",
        "source_kind": "chunk",
        "root_entry_id": root_entry.get("id"),
        "file_name": metadata.get("file_name"),
        "file_type": metadata.get("file_type"),
        "document_archetype": archetype,
        "output_dir": str(processed_document.get("output_dir") or ""),
        "heading": root_entry.get("title"),
        "heading_path": heading_path,
        "heading_path_text": heading_path_text,
        "text": text,
        "locator": locator,
        "locator_path": locator_path,
        "position_text": format_position(locator),
        "metadata": {
            "kind": root_entry.get("kind"),
            "level": root_entry.get("level"),
            "block_positions": list(sorted(set(int(pos) for pos in positions))),
            "primary_structure": content.get("document_profile", {}).get("primary_structure"),
            "text_length": len(text),
            "token_count": len(text.split()),
        },
        "embedding": None,
    }

    if root_context:
        chunk["metadata"]["root_context"] = root_context
        for key, value in root_context.items():
            chunk["metadata"].setdefault(key, value)

    return chunk


def _normative_chunk_roots(flat_entries: list[dict]) -> list[dict]:
    roots = [item for item in flat_entries if item["entry"].get("kind") == "article"]
    return roots or flat_entries


def _amending_chunk_roots(flat_entries: list[dict], root_entries: Sequence[dict]) -> list[dict]:
    root_articles = [entry for entry in root_entries if entry.get("kind") == "article"]
    selected: list[dict] = []

    for root_article in root_articles:
        root_position = _entry_block_position(root_article.get("id"))
        root_flat = next(
            (item for item in flat_entries if item["entry"].get("id") == root_article.get("id")),
            None,
        )
        descendant_articles = [
            item
            for item in flat_entries
            if item["entry"].get("kind") == "article"
            and item["entry"].get("id") != root_article.get("id")
            and root_article in item["ancestors"]
        ]
        if descendant_articles:
            for descendant in descendant_articles:
                descendant["root_context"] = {
                    "act_article_title": root_article.get("title"),
                    "act_article_id": root_article.get("id"),
                    "act_article_position": root_position,
                }
            selected.extend(descendant_articles)
            continue
        if root_flat:
            selected.append(root_flat)

    return selected or [item for item in flat_entries if item["entry"].get("kind") == "article"]


def _manual_chunk_roots(flat_entries: list[dict], block_by_position: dict[int, dict]) -> list[dict]:
    selected: list[dict] = []

    def heading_group(item: dict) -> str | None:
        position = _entry_block_position(item["entry"].get("id"))
        block = block_by_position.get(position, {})
        extra = block.get("extra", {}) or {}
        return extra.get("heading_group") or extra.get("manual_group")

    for item in flat_entries:
        entry = item["entry"]
        if entry.get("kind") != "heading":
            continue
        level = entry.get("level")
        if not isinstance(level, int) or level < 2:
            continue
        group = heading_group(item)
        if group in {"document_title", "interface"}:
            continue

        descendant_heading_levels = [
            child.get("level")
            for child in entry.get("children") or []
            if child.get("kind") == "heading"
        ]
        if level == 2 and any(isinstance(child_level, int) and child_level == 3 for child_level in descendant_heading_levels):
            continue

        selected.append(item)

    return selected or [item for item in flat_entries if item["entry"].get("kind") == "heading"]


def _manual_heading_level(block: dict) -> int:
    extra = block.get("extra", {}) or {}
    level = extra.get("heading_level")
    return level if isinstance(level, int) else 1


def _manual_heading_group(block: dict) -> str:
    extra = block.get("extra", {}) or {}
    return str(extra.get("heading_group") or extra.get("manual_group") or "")


def _manual_is_interface_heading(block: dict) -> bool:
    return _manual_heading_group(block) == "interface"


def _manual_is_leaf_heading(blocks: Sequence[dict], start_position: int) -> bool:
    current_block = blocks[start_position - 1]
    current_level = _manual_heading_level(current_block)

    for next_block in blocks[start_position:]:
        if next_block.get("kind") != "heading":
            continue
        if _manual_is_interface_heading(next_block):
            continue
        next_level = _manual_heading_level(next_block)
        if next_level > current_level:
            return False
        return True

    return True


def _build_manual_chunks(processed_document: dict, *, start_index: int) -> list[dict]:
    content = dict(processed_document.get("content", {}) or {})
    blocks = list(content.get("blocks", []) or [])
    heading_stack: list[dict] = []
    current_interface: dict | None = None
    heading_infos: list[dict] = []
    covered_heading_positions: set[int] = set()
    chunks: list[dict] = []
    chunk_index = start_index

    def current_heading_path() -> list[str]:
        return [str(item.get("title") or "").strip() for item in heading_stack if str(item.get("title") or "").strip()]

    for position, block in enumerate(blocks, start=1):
        kind = block.get("kind")
        extra = block.get("extra", {}) or {}
        if kind == "heading":
            level = _manual_heading_level(block)
            title = str(block.get("display_title") or block.get("title") or "").strip()
            group = _manual_heading_group(block)
            heading_stack = [item for item in heading_stack if int(item.get("level") or 0) < level]
            if _manual_is_interface_heading(block):
                current_interface = {"title": title, "level": level, "position": position}
                continue

            current_interface = None
            heading_info = {
                "title": title,
                "level": level,
                "position": position,
                "group": group,
                "path": current_heading_path() + ([title] if title else []),
            }
            heading_stack.append(heading_info)
            heading_infos.append(heading_info)
            continue

        if kind != "paragraph":
            continue

        manual_group = str(extra.get("manual_group") or "body")
        if manual_group == "overview":
            continue
        if manual_group == "interface_label":
            current_interface = {
                "title": str(block.get("display_title") or block.get("title") or block.get("text") or "").strip(),
                "position": position,
            }

        heading_path = current_heading_path()
        if not heading_path:
            fallback_title = str(block.get("display_title") or block.get("title") or f"Bloco {position}")
            heading_path = [fallback_title]

        if heading_stack:
            covered_heading_positions.add(int(heading_stack[-1]["position"]))

        root_context = {"manual_group": manual_group}
        if current_interface and current_interface.get("title"):
            root_context["interface_context"] = current_interface["title"]

        root_title = heading_path[-1]
        pseudo_entry = {
            "id": block.get("id"),
            "title": root_title,
            "kind": "paragraph" if manual_group in {"interface_label", "list_item", "micro_action"} else "heading",
            "level": len(heading_path),
            "locator": dict(block.get("locator", {}) or {}),
        }
        chunk = _chunk_record(
            chunk_index=chunk_index,
            processed_document=processed_document,
            root_entry=pseudo_entry,
            heading_path=heading_path,
            positions=(position,),
            root_context=root_context,
        )
        if chunk:
            chunks.append(chunk)
            chunk_index += 1

    for heading_info in heading_infos:
        if heading_info["position"] in covered_heading_positions:
            continue
        if heading_info["group"] in {"document_title", "styled_heading"}:
            continue
        if not _manual_is_leaf_heading(blocks, int(heading_info["position"])):
            continue
        heading_block = blocks[int(heading_info["position"]) - 1]
        pseudo_entry = {
            "id": heading_block.get("id"),
            "title": heading_info["title"],
            "kind": heading_block.get("kind"),
            "level": heading_info["level"],
            "locator": dict(heading_block.get("locator", {}) or {}),
        }
        chunk = _chunk_record(
            chunk_index=chunk_index,
            processed_document=processed_document,
            root_entry=pseudo_entry,
            heading_path=list(heading_info["path"] or []),
            positions=(int(heading_info["position"]),),
            root_context={"manual_group": heading_info["group"] or "heading_only"},
        )
        if chunk:
            chunks.append(chunk)
            chunk_index += 1

    return chunks


def _generic_chunks_from_blocks(processed_document: dict, *, start_index: int) -> list[dict]:
    metadata = dict(processed_document.get("metadata", {}) or {})
    content = dict(processed_document.get("content", {}) or {})
    blocks = list(content.get("blocks", []) or [])
    chunks: list[dict] = []

    group: list[tuple[int, dict]] = []
    chunk_index = start_index
    for position, block in enumerate(blocks, start=1):
        if not str(block.get("text") or "").strip():
            continue
        group.append((position, block))
        if len(group) < 3:
            continue

        positions = [pos for pos, _ in group]
        text = "\n\n".join(str(item.get("text") or "").strip() for _, item in group).strip()
        locator = dict(group[0][1].get("locator", {}) or {})
        chunks.append(
            {
                "chunk_id": f"chunk_{chunk_index:05d}",
                "source_kind": "chunk",
                "root_entry_id": None,
                "file_name": metadata.get("file_name"),
                "file_type": metadata.get("file_type"),
                "document_archetype": content.get("document_archetype") or metadata.get("document_archetype") or "generic_document",
                "output_dir": str(processed_document.get("output_dir") or ""),
                "heading": group[0][1].get("display_title") or group[0][1].get("title"),
                "heading_path": list(group[0][1].get("hierarchy_path") or []),
                "heading_path_text": _resolved_heading_path_text(
                    list(group[0][1].get("hierarchy_path") or []),
                    fallback_title=group[0][1].get("display_title") or group[0][1].get("title"),
                ),
                "text": text,
                "locator": locator,
                "locator_path": _resolved_locator_path(
                    locator,
                    list(group[0][1].get("hierarchy_path") or []),
                    fallback_title=group[0][1].get("display_title") or group[0][1].get("title"),
                ),
                "position_text": format_position(locator),
                "metadata": {
                    "kind": "block_group",
                    "level": 1,
                    "block_positions": positions,
                    "primary_structure": content.get("document_profile", {}).get("primary_structure"),
                    "text_length": len(text),
                    "token_count": len(text.split()),
                },
                "embedding": None,
            }
        )
        chunk_index += 1
        group = []

    if group:
        positions = [pos for pos, _ in group]
        text = "\n\n".join(str(item.get("text") or "").strip() for _, item in group).strip()
        locator = dict(group[0][1].get("locator", {}) or {})
        chunks.append(
            {
                "chunk_id": f"chunk_{chunk_index:05d}",
                "source_kind": "chunk",
                "root_entry_id": None,
                "file_name": metadata.get("file_name"),
                "file_type": metadata.get("file_type"),
                "document_archetype": content.get("document_archetype") or metadata.get("document_archetype") or "generic_document",
                "output_dir": str(processed_document.get("output_dir") or ""),
                "heading": group[0][1].get("display_title") or group[0][1].get("title"),
                "heading_path": list(group[0][1].get("hierarchy_path") or []),
                "heading_path_text": _resolved_heading_path_text(
                    list(group[0][1].get("hierarchy_path") or []),
                    fallback_title=group[0][1].get("display_title") or group[0][1].get("title"),
                ),
                "text": text,
                "locator": locator,
                "locator_path": _resolved_locator_path(
                    locator,
                    list(group[0][1].get("hierarchy_path") or []),
                    fallback_title=group[0][1].get("display_title") or group[0][1].get("title"),
                ),
                "position_text": format_position(locator),
                "metadata": {
                    "kind": "block_group",
                    "level": 1,
                    "block_positions": positions,
                    "primary_structure": content.get("document_profile", {}).get("primary_structure"),
                    "text_length": len(text),
                    "token_count": len(text.split()),
                },
                "embedding": None,
            }
        )

    return chunks


def build_document_chunks(processed_document: dict, *, start_index: int = 1) -> list[dict]:
    metadata = dict(processed_document.get("metadata", {}) or {})
    content = dict(processed_document.get("content", {}) or {})
    index_entries = list(processed_document.get("index", []) or [])
    blocks = list(content.get("blocks", []) or [])
    block_by_position = {index: block for index, block in enumerate(blocks, start=1)}
    archetype: DocumentArchetype = (
        content.get("document_archetype")
        or metadata.get("document_archetype")
        or "generic_document"
    )

    flat_entries = list(_iter_entries(index_entries))
    if archetype == "legislation_normative":
        selected_roots = _normative_chunk_roots(flat_entries)
    elif archetype == "legislation_amending_act":
        selected_roots = _amending_chunk_roots(flat_entries, index_entries)
    elif archetype == "manual_procedural":
        manual_chunks = _build_manual_chunks(processed_document, start_index=start_index)
        if manual_chunks:
            return manual_chunks
        selected_roots = _manual_chunk_roots(flat_entries, block_by_position)
    else:
        selected_roots = [item for item in flat_entries if item["entry"].get("kind") == "heading"]

    chunks: list[dict] = []
    chunk_index = start_index
    seen_positions: set[tuple[int, ...]] = set()
    for item in selected_roots:
        if archetype in {"manual_procedural", "generic_document"} and item["entry"].get("kind") == "heading":
            positions = tuple(_heading_span_positions(item["entry"], block_by_position))
        else:
            positions = tuple(_descendant_block_positions(item["entry"]))
        if not positions or positions in seen_positions:
            continue
        seen_positions.add(positions)
        chunk = _chunk_record(
            chunk_index=chunk_index,
            processed_document=processed_document,
            root_entry=item["entry"],
            heading_path=item["path"],
            positions=positions,
            root_context=item.get("root_context"),
        )
        if chunk:
            chunks.append(chunk)
            chunk_index += 1

    if chunks:
        return chunks
    return _generic_chunks_from_blocks(processed_document, start_index=start_index)


def build_collection_chunks(processed_documents: Sequence[dict]) -> list[dict]:
    chunks: list[dict] = []
    chunk_index = 1

    for processed_document in processed_documents:
        document_chunks = build_document_chunks(processed_document, start_index=chunk_index)
        chunks.extend(document_chunks)
        chunk_index += len(document_chunks)

    return chunks
