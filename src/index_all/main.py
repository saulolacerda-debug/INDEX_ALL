from __future__ import annotations

import argparse
from pathlib import Path

from index_all.config import get_settings
from index_all.indexing.consultation_payload import (
    build_ai_context_payload,
    build_content_payload,
    build_index_payload,
    build_metadata_payload,
)
from index_all.indexing.metadata_extractor import extract_common_metadata
from index_all.indexing.structure_indexer import build_structure_index
from index_all.indexing.summary_builder import build_summary
from index_all.ingestion.file_router import get_parser_for_path, is_ignored_path
from index_all.outputs.html_writer import write_report_html
from index_all.outputs.json_writer import write_json
from index_all.outputs.markdown_writer import write_ai_context_markdown, write_summary_markdown
from index_all.utils.logging_utils import configure_logging, get_logger
from index_all.utils.paths import ensure_dir, unique_output_dir


logger = get_logger(__name__)


def _contains_only_ignored_files(input_path: Path) -> bool:
    if not input_path.is_dir():
        return False

    seen_file = False
    for path in input_path.rglob("*"):
        if not path.is_file():
            continue
        seen_file = True
        if not is_ignored_path(path):
            return False
    return seen_file


def iter_supported_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if is_ignored_path(input_path):
            return []
        return [input_path]

    files = []
    for path in input_path.rglob("*"):
        if path.is_file() and not is_ignored_path(path):
            files.append(path)
    return sorted(files)


def process_file(file_path: Path, output_root: Path) -> Path:
    parser = get_parser_for_path(file_path)
    parsed = parser(file_path)

    metadata = extract_common_metadata(file_path)
    content = parsed.get("content", {"blocks": [], "parser_metadata": {}})
    blocks = content.get("blocks", [])
    index_entries = build_structure_index(blocks)
    summary = build_summary(metadata, blocks, index_entries)
    consultation_payload = build_content_payload(metadata, content, index_entries, summary)
    metadata_payload = build_metadata_payload(metadata, consultation_payload)
    index_payload = build_index_payload(metadata, consultation_payload)
    ai_context_payload = build_ai_context_payload(metadata_payload, consultation_payload, index_payload)

    output_dir = unique_output_dir(output_root, file_path.stem)

    write_json(output_dir / "ai_context.json", ai_context_payload)
    write_json(output_dir / "metadata.json", metadata_payload)
    write_json(output_dir / "content.json", consultation_payload)
    write_json(output_dir / "index.json", index_payload)
    write_ai_context_markdown(output_dir / "ai_context.md", ai_context_payload)
    write_summary_markdown(output_dir / "summary.md", consultation_payload)
    write_report_html(output_dir / "report.html", metadata, consultation_payload, index_entries, summary)

    logger.info("Processed %s -> %s", file_path.name, output_dir)
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="INDEX_ALL - universal file indexer")
    parser.add_argument("input_path", help="Path to a file or directory")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to data/processed",
    )
    return parser


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    settings = get_settings()
    output_root = Path(args.output_dir).resolve() if args.output_dir else settings.processed_dir
    ensure_dir(output_root)

    files = iter_supported_files(input_path)
    if not files:
        if input_path.is_file() and is_ignored_path(input_path):
            return
        if _contains_only_ignored_files(input_path):
            return
        logger.warning("No files found in %s", input_path)
        return

    supported = 0
    skipped = 0
    for file_path in files:
        try:
            process_file(file_path, output_root)
            supported += 1
        except ValueError as exc:
            skipped += 1
            logger.warning("Skipping %s: %s", file_path, exc)
        except Exception as exc:  # pragma: no cover
            skipped += 1
            logger.exception("Failed processing %s: %s", file_path, exc)

    logger.info("Done. Supported=%s | Skipped=%s", supported, skipped)


if __name__ == "__main__":
    main()
