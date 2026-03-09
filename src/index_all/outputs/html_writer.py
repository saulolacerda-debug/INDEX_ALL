from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


KIND_LABELS = {
    "preamble": "Preâmbulo",
    "part": "Parte",
    "book": "Livro",
    "title": "Título",
    "chapter": "Capítulo",
    "section": "Seção",
    "subsection": "Subseção",
    "article": "Artigo",
    "legal_paragraph": "Parágrafo",
    "inciso": "Inciso",
    "alinea": "Alínea",
    "item": "Item",
    "heading": "Cabeçalho",
    "paragraph": "Parágrafo",
    "table": "Tabela",
    "page_text": "Página",
    "line": "Linha",
    "list_item": "Item de lista",
    "xml_node": "Nó XML",
    "table_header": "Cabeçalho de tabela",
    "table_row": "Linha de tabela",
    "sheet": "Planilha",
    "sheet_row": "Linha de planilha",
    "h1": "H1",
    "h2": "H2",
    "h3": "H3",
    "p": "Parágrafo HTML",
    "li": "Item",
    "title_block": "Título",
}

LOCATOR_KEYS = ("part", "book", "title", "chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item")


def _kind_label(kind: str | None) -> str:
    if not kind:
        return "Bloco"
    return KIND_LABELS.get(kind, kind.replace("_", " ").title())


def _flatten_index_count(entries: list[dict]) -> int:
    count = 0
    for entry in entries:
        count += 1
        count += _flatten_index_count(entry.get("children") or [])
    return count


def _format_locator_path(locator: dict) -> str | None:
    parts = []
    for key in LOCATOR_KEYS:
        value = locator.get(key)
        if value:
            parts.append(str(value))
    if not parts:
        return None
    return " > ".join(parts)


def _format_position(locator: dict) -> str | None:
    page = locator.get("page")
    line_start = locator.get("line_start")
    line_end = locator.get("line_end")

    parts = []
    if page:
        parts.append(f"Página {page}")
    if line_start and line_end and line_start == line_end:
        parts.append(f"Linha {line_start}")
    elif line_start and line_end:
        parts.append(f"Linhas {line_start}-{line_end}")
    elif line_start:
        parts.append(f"Linha {line_start}")
    return " | ".join(parts) or None


def _fallback_title(block: dict, fallback_index: int) -> str:
    text = (block.get("text") or "").strip()
    extra = block.get("extra", {})
    display_title = block.get("display_title")
    if display_title:
        return str(display_title)
    title = block.get("title")
    if extra.get("display_title"):
        return str(extra["display_title"])
    if title:
        return str(title)
    if not text:
        return f"Bloco {fallback_index}"
    preview = " ".join(text.split())
    if len(preview) <= 96:
        return preview
    return f"{preview[:93].rstrip()}..."


def _build_block_payload(blocks: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for index, block in enumerate(blocks, start=1):
        locator = block.get("locator", {})
        anchor = f"block-{index:04d}"
        payload.append(
            {
                "anchor": anchor,
                "block_id": block.get("id"),
                "kind": block.get("kind"),
                "kind_label": _kind_label(block.get("kind")),
                "title": _fallback_title(block, index),
                "text": block.get("text") or "",
                "locator": locator,
                "locator_text": _format_locator_path(locator),
                "position_text": _format_position(locator),
                "manual_group": (block.get("extra") or {}).get("manual_group"),
            }
        )
    return payload


def _attach_anchors(entries: list[dict], blocks: list[dict]) -> list[dict]:
    anchored_entries: list[dict] = []
    for entry in entries:
        try:
            block_position = int(str(entry.get("id", "")).split("_")[-1])
        except ValueError:
            block_position = None

        anchor = None
        if block_position and 1 <= block_position <= len(blocks):
            anchor = blocks[block_position - 1]["anchor"]

        anchored_entries.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "kind": entry.get("kind"),
                "kind_label": _kind_label(entry.get("kind")),
                "locator": entry.get("locator", {}),
                "locator_text": _format_locator_path(entry.get("locator", {})),
                "level": entry.get("level"),
                "parent_id": entry.get("parent_id"),
                "anchor": anchor,
                "children": _attach_anchors(entry.get("children") or [], blocks),
            }
        )
    return anchored_entries


def _build_stats(blocks: list[dict], index_entries: list[dict]) -> dict:
    kind_counts = Counter(block.get("kind") or "unknown" for block in blocks)
    return {
        "block_count": len(blocks),
        "index_entry_count": _flatten_index_count(index_entries),
        "kind_counts": [
            {"kind": kind, "label": _kind_label(kind), "count": count}
            for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _build_payload(metadata: dict, content: dict, index_entries: list[dict], summary: str) -> dict:
    blocks = _build_block_payload(content.get("blocks", []))
    return {
        "metadata": metadata,
        "document_profile": content.get("document_profile", {}),
        "parser_metadata": content.get("parser_metadata", {}),
        "summary": summary,
        "stats": _build_stats(blocks, index_entries),
        "blocks": blocks,
        "index": _attach_anchors(index_entries, blocks),
    }


def _build_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = payload["metadata"].get("file_name", "INDEX_ALL Report")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | INDEX_ALL</title>
  <style>
    :root {{
      color-scheme: light;
      --color-blue-900: #07306C;
      --color-blue-700: #046B91;
      --color-blue-600: #075EAD;
      --color-teal-500: #499A9E;
      --color-gold-500: #DF9E51;
      --color-neutral-950: #0F172A;
      --color-neutral-800: #334155;
      --color-neutral-200: #CBD5E1;
      --color-neutral-0: #FFFFFF;
      --color-bg-cold: #D8E9F8;
      --color-bg-soft: #ECF7F7;
      --color-bg-warm: #FFF4E5;
      --color-bg-warm-light: #FFF8EA;
      --bg: var(--color-bg-soft);
      --panel: rgba(255, 255, 255, 0.92);
      --panel-strong: var(--color-neutral-0);
      --panel-alt: var(--color-bg-soft);
      --border: rgba(203, 213, 225, 0.92);
      --border-strong: rgba(51, 65, 85, 0.24);
      --text: var(--color-neutral-950);
      --muted: var(--color-neutral-800);
      --accent: var(--color-blue-700);
      --accent-hover: var(--color-blue-600);
      --accent-soft: rgba(4, 107, 145, 0.12);
      --accent-strong: var(--color-blue-900);
      --accent-teal-soft: rgba(73, 154, 158, 0.16);
      --accent-gold-soft: rgba(223, 158, 81, 0.20);
      --shadow: 0 18px 45px rgba(7, 48, 108, 0.12);
      --radius: 20px;
      --paper-width: 210mm;
      --mono: "Consolas", "Courier New", monospace;
      --sans: "Trebuchet MS", "Segoe UI", sans-serif;
      --serif: "Palatino Linotype", "Book Antiqua", Georgia, serif;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      color: var(--text);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(7, 94, 173, 0.16), transparent 28rem),
        radial-gradient(circle at bottom right, rgba(73, 154, 158, 0.12), transparent 24rem),
        linear-gradient(180deg, var(--color-bg-warm-light) 0%, var(--bg) 52%, var(--color-neutral-0) 100%);
    }}

    .shell {{
      min-height: 100vh;
      padding: 24px;
    }}

    .hero {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: end;
      justify-content: space-between;
      margin-bottom: 18px;
      padding: 22px 26px;
      border: 1px solid var(--border);
      border-radius: calc(var(--radius) + 6px);
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(236, 247, 247, 0.96), rgba(216, 233, 248, 0.92));
      box-shadow: var(--shadow);
    }}

    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 0.83rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      font-family: var(--serif);
      font-size: clamp(1.8rem, 2.2vw, 2.8rem);
      line-height: 1.05;
    }}

    .subtitle {{
      margin: 10px 0 0;
      max-width: 72ch;
      color: var(--muted);
      line-height: 1.5;
    }}

    .hero-meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .pill {{
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.84);
      font-size: 0.92rem;
      color: var(--muted);
    }}

    .workspace {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}

    .panel {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}

    .panel-header {{
      padding: 18px 20px 14px;
      border-bottom: 1px solid var(--border);
    }}

    .panel-title {{
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
    }}

    .panel-subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.45;
    }}

    .panel-body {{
      padding: 18px 20px 20px;
      overflow-x: auto;
    }}

    .sticky {{
      position: sticky;
      top: 24px;
      max-height: calc(100vh - 48px);
      overflow-y: auto;
      overflow-x: auto;
    }}

    .controls {{
      display: grid;
      gap: 12px;
      margin-bottom: 16px;
    }}

    .field {{
      display: grid;
      gap: 6px;
    }}

    .field label {{
      font-size: 0.84rem;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .field input,
    .field select {{
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 11px 12px;
      background: var(--color-neutral-0);
      color: var(--text);
      font: inherit;
    }}

    .tree-root,
    .tree-children {{
      list-style: none;
      margin: 0;
      padding: 0;
    }}

    .tree-root {{
      width: max-content;
      min-width: 100%;
    }}

    .tree-node {{
      margin: 6px 0;
    }}

    .tree-children {{
      margin-left: 16px;
      padding-left: 10px;
      border-left: 1px dashed rgba(4, 107, 145, 0.20);
    }}

    details.tree-group > summary {{
      list-style: none;
    }}

    details.tree-group > summary::-webkit-details-marker {{
      display: none;
    }}

    .tree-button {{
      width: max-content;
      min-width: 100%;
      display: grid;
      gap: 4px;
      text-align: left;
      border: 1px solid transparent;
      border-radius: 14px;
      padding: 10px 12px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      transition: background 120ms ease, border-color 120ms ease, transform 120ms ease;
    }}

    .tree-button:hover {{
      background: rgba(216, 233, 248, 0.42);
      border-color: rgba(4, 107, 145, 0.16);
      transform: translateX(1px);
    }}

    .tree-button.selected {{
      background: var(--accent-soft);
      border-color: rgba(4, 107, 145, 0.22);
    }}

    .tree-topline {{
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(236, 247, 247, 0.96);
      border: 1px solid var(--border);
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 700;
      white-space: nowrap;
    }}

    .search-hit {{
      padding: 0 0.18em;
      border-radius: 0.28em;
      background: rgba(223, 158, 81, 0.32);
      box-shadow: inset 0 -0.55em 0 rgba(223, 158, 81, 0.18);
    }}

    .tree-title,
    .block-title {{
      font-weight: 700;
      line-height: 1.35;
    }}

    .tree-locator,
    .meta-value,
    .hint,
    .block-meta {{
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.45;
    }}

    .content-panel {{
      min-width: 0;
      overflow: hidden;
    }}

    .content-panel .panel-header {{
      position: sticky;
      top: 0;
      z-index: 4;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(236, 247, 247, 0.94));
      backdrop-filter: blur(12px);
    }}

    .content-toolbar {{
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      overflow-x: auto;
    }}

    .selection-bar {{
      display: flex;
      gap: 14px;
      align-items: start;
      justify-content: space-between;
      margin-top: 14px;
      padding: 14px 16px;
      border: 1px solid rgba(4, 107, 145, 0.12);
      border-radius: 18px;
      background: rgba(236, 247, 247, 0.72);
      overflow-x: auto;
    }}

    .selection-copy {{
      display: grid;
      gap: 8px;
      min-width: 0;
    }}

    .selection-title {{
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      line-height: 1.4;
    }}

    .breadcrumb {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .crumb {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(223, 158, 81, 0.26);
      background: rgba(255, 248, 234, 0.98);
      color: var(--accent-strong);
      font-size: 0.84rem;
      font-weight: 700;
    }}

    .toolbar-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }}

    .content-stats {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .stat-card {{
      padding: 12px 14px;
      border-radius: 16px;
      background: var(--panel-strong);
      border: 1px solid var(--border);
      min-width: 120px;
    }}

    .stat-card strong {{
      display: block;
      font-size: 1.2rem;
      font-family: var(--serif);
    }}

    .block-list {{
      display: grid;
      gap: 14px;
      width: 100%;
      justify-items: center;
    }}

    .content-scroll {{
      padding: 20px;
      overflow-y: auto;
      overflow-x: auto;
    }}

    .block-card {{
      width: min(100%, var(--paper-width));
      max-width: var(--paper-width);
      padding: 18px 20px;
      border: 1px solid rgba(203, 213, 225, 0.92);
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(236, 247, 247, 0.52));
      transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
      scroll-margin-top: 28px;
      overflow-x: auto;
    }}

    .block-card:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 30px rgba(7, 48, 108, 0.08);
    }}

    .block-card.selected {{
      border-color: rgba(4, 107, 145, 0.34);
      box-shadow: 0 14px 36px rgba(4, 107, 145, 0.14);
    }}

    .block-header {{
      display: flex;
      gap: 12px;
      align-items: start;
      justify-content: space-between;
      margin-bottom: 10px;
    }}

    .block-title-group {{
      display: grid;
      gap: 7px;
      min-width: 0;
    }}

    .block-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .anchor-link {{
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.92);
      color: var(--accent);
      border-radius: 12px;
      padding: 8px 10px;
      text-decoration: none;
      font-size: 0.88rem;
      white-space: nowrap;
    }}

    .anchor-link:hover {{
      color: var(--accent-hover);
      border-color: rgba(4, 107, 145, 0.18);
    }}

    .copy-button {{
      border: 1px solid rgba(4, 107, 145, 0.22);
      background: rgba(255, 255, 255, 0.94);
      color: var(--accent);
      border-radius: 12px;
      padding: 8px 10px;
      font: inherit;
      font-size: 0.88rem;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }}

    .copy-button:hover {{
      transform: translateY(-1px);
      border-color: rgba(7, 94, 173, 0.28);
      background: rgba(216, 233, 248, 0.46);
    }}

    .copy-button.copied {{
      background: rgba(73, 154, 158, 0.16);
      border-color: rgba(73, 154, 158, 0.28);
      color: var(--color-blue-900);
    }}

    .copy-button:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
      transform: none;
    }}

    .block-text {{
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: break-word;
      word-break: normal;
      hyphens: auto;
      font-size: 0.98rem;
      line-height: 1.65;
      color: var(--text);
      padding-left: 12px;
    }}

    .stack {{
      display: grid;
      gap: 14px;
    }}

    .meta-grid {{
      display: grid;
      gap: 10px;
    }}

    .meta-item {{
      padding: 12px 14px;
      border-radius: 15px;
      background: var(--panel-strong);
      border: 1px solid var(--border);
    }}

    .meta-label {{
      display: block;
      margin-bottom: 4px;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    .summary-card {{
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255, 248, 234, 0.98), rgba(255, 244, 229, 0.94));
      border: 1px solid var(--border);
      border-left: 6px solid var(--color-gold-500);
    }}

    .summary-text {{
      margin: 0;
      white-space: pre-wrap;
      line-height: 1.65;
      color: var(--text);
    }}

    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .empty-state {{
      padding: 18px;
      border: 1px dashed rgba(73, 154, 158, 0.30);
      border-radius: 16px;
      color: var(--muted);
      background: rgba(236, 247, 247, 0.60);
    }}

    @media (max-width: 1180px) {{
      .workspace {{
        grid-template-columns: 1fr;
      }}

      .sticky {{
        position: static;
        max-height: none;
      }}

      .selection-bar {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">INDEX_ALL Report</p>
        <h1 id="hero-title"></h1>
        <p class="subtitle" id="hero-subtitle"></p>
      </div>
      <div class="hero-meta" id="hero-meta"></div>
    </section>

    <section class="workspace">
      <aside class="panel sticky">
        <div class="panel-header">
          <h2 class="panel-title">Navegação</h2>
          <p class="panel-subtitle">Árvore estrutural do documento com busca e filtro por tipo.</p>
        </div>
        <div class="panel-body">
          <div class="controls">
            <div class="field">
              <label for="search-input">Buscar</label>
              <input id="search-input" type="search" placeholder="Art. 156-A, Seção V-A, IBS...">
            </div>
            <div class="field">
              <label for="kind-filter">Tipo de bloco</label>
              <select id="kind-filter">
                <option value="all">Todos</option>
              </select>
            </div>
          </div>
          <div id="tree-root"></div>
        </div>
      </aside>

      <main class="panel content-panel">
        <div class="panel-header">
          <div class="content-toolbar">
            <div>
              <h2 class="panel-title">Conteúdo</h2>
              <p class="panel-subtitle">Trechos extraídos com navegação sincronizada pelo índice.</p>
            </div>
            <div class="content-stats" id="content-stats"></div>
          </div>
          <div class="selection-bar">
            <div class="selection-copy">
              <div class="hint">Contexto selecionado</div>
              <p class="selection-title" id="selected-title"></p>
              <div class="block-meta" id="selected-meta"></div>
              <div class="breadcrumb" id="selected-breadcrumb"></div>
            </div>
            <div class="toolbar-actions">
              <button class="copy-button" id="copy-struct-link-button" type="button">Copiar link estrutural</button>
              <button class="copy-button" id="export-selected-button" type="button">Exportar trecho</button>
            </div>
          </div>
        </div>
        <div class="content-scroll">
          <div class="block-list" id="block-list"></div>
        </div>
      </main>
    </section>
  </div>

  <script id="report-data" type="application/json">{data_json}</script>
  <script>
    const data = JSON.parse(document.getElementById("report-data").textContent);
    const blocksByAnchor = Object.fromEntries(data.blocks.map((block) => [block.anchor, block]));
    const locatorKeys = ["part", "book", "title", "chapter", "section", "subsection", "article", "paragraph", "inciso", "alinea", "item"];

    const state = {{
      query: "",
      kind: "all",
      selectedAnchor: null,
      copiedAnchor: null,
    }};

    function normalizeText(value) {{
      return String(value || "")
        .normalize("NFD")
        .replace(/[\\u0300-\\u036f]/g, "")
        .toLowerCase();
    }}

    function buildNormalizedMap(value) {{
      const source = String(value || "");
      let normalized = "";
      const sourceIndexMap = [];

      for (let index = 0; index < source.length; index += 1) {{
        const normalizedChunk = source[index]
          .normalize("NFD")
          .replace(/[\\u0300-\\u036f]/g, "")
          .toLowerCase();

        for (const character of normalizedChunk) {{
          normalized += character;
          sourceIndexMap.push(index);
        }}
      }}

      return {{ source, normalized, sourceIndexMap }};
    }}

    function escapeHtml(value) {{
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function highlightText(value) {{
      const source = String(value || "");
      const query = normalizeText(state.query).trim();
      if (!query) {{
        return escapeHtml(source);
      }}

      const {{ normalized, sourceIndexMap }} = buildNormalizedMap(source);
      let currentIndex = 0;
      let lastSourceIndex = 0;
      let html = "";

      while (currentIndex < normalized.length) {{
        const matchIndex = normalized.indexOf(query, currentIndex);
        if (matchIndex === -1) {{
          break;
        }}

        const sourceStart = sourceIndexMap[matchIndex];
        const sourceEnd = sourceIndexMap[matchIndex + query.length - 1] + 1;
        html += escapeHtml(source.slice(lastSourceIndex, sourceStart));
        html += "<mark class=\\"search-hit\\">" + escapeHtml(source.slice(sourceStart, sourceEnd)) + "</mark>";
        lastSourceIndex = sourceEnd;
        currentIndex = matchIndex + query.length;
      }}

      html += escapeHtml(source.slice(lastSourceIndex));
      return html;
    }}

    function matchesBlock(block) {{
      const query = normalizeText(state.query);
      const haystack = normalizeText([block.kind_label, block.title, block.text, block.locator_text].join(" "));
      const queryMatch = !query || haystack.includes(query);
      const kindMatch = state.kind === "all" || block.kind === state.kind;
      return queryMatch && kindMatch;
    }}

    function getSelectedBlock() {{
      if (!state.selectedAnchor) {{
        return null;
      }}
      return blocksByAnchor[state.selectedAnchor] || null;
    }}

    function getBreadcrumbParts(block) {{
      if (!block) {{
        return [];
      }}

      const parts = locatorKeys
        .map((key) => block.locator && block.locator[key])
        .filter(Boolean);

      if (parts.length) {{
        return parts;
      }}
      return block.title ? [block.title] : [];
    }}

    function getDeepLinkReference(block) {{
      const parts = getBreadcrumbParts(block);
      if (parts.length) {{
        return parts.join(" > ");
      }}
      return block && block.title ? block.title : "";
    }}

    function buildStructuralLink(block) {{
      const reference = getDeepLinkReference(block);
      const baseUrl = window.location.href.split("#")[0];
      return baseUrl + "#ref=" + encodeURIComponent(reference);
    }}

    function resolveReference(reference) {{
      const normalizedReference = normalizeText(reference).trim();
      if (!normalizedReference) {{
        return null;
      }}

      const exactMatch = data.blocks.find((block) => {{
        const candidates = [
          block.title,
          block.locator_text,
          ...(locatorKeys.map((key) => block.locator && block.locator[key])),
        ]
          .filter(Boolean)
          .map(normalizeText);
        return candidates.some((candidate) => candidate === normalizedReference);
      }});

      if (exactMatch) {{
        return exactMatch.anchor;
      }}

      const partialMatch = data.blocks.find((block) => {{
        const candidates = [
          block.title,
          block.locator_text,
          ...(locatorKeys.map((key) => block.locator && block.locator[key])),
        ]
          .filter(Boolean)
          .map(normalizeText);
        return candidates.some((candidate) => candidate.includes(normalizedReference) || normalizedReference.includes(candidate));
      }});

      return partialMatch ? partialMatch.anchor : null;
    }}

    function resolveHashTarget() {{
      const rawHash = decodeURIComponent(window.location.hash.replace(/^#/, ""));
      if (!rawHash) {{
        return null;
      }}

      if (blocksByAnchor[rawHash]) {{
        return {{ anchor: rawHash, hashValue: "#" + rawHash }};
      }}

      if (rawHash.startsWith("ref=")) {{
        const anchor = resolveReference(rawHash.slice(4));
        return anchor ? {{ anchor, hashValue: "#" + rawHash }} : null;
      }}

      const anchor = resolveReference(rawHash);
      return anchor ? {{ anchor, hashValue: "#" + rawHash }} : null;
    }}

    function filterIndexNodes(nodes) {{
      const filtered = [];
      for (const node of nodes) {{
        const block = node.anchor ? blocksByAnchor[node.anchor] : null;
        const children = filterIndexNodes(node.children || []);
        const selfMatches = block ? matchesBlock(block) : false;
        if (selfMatches || children.length) {{
          filtered.push({{ ...node, children }});
        }}
      }}
      return filtered;
    }}

    function nodeContainsSelected(node) {{
      if (node.anchor && node.anchor === state.selectedAnchor) {{
        return true;
      }}
      return (node.children || []).some(nodeContainsSelected);
    }}

    function renderHero() {{
      const archetype = data.document_profile && data.document_profile.document_archetype;
      const subtitles = {{
        legislation_normative: "Relatório navegável com hierarquia normativa completa do documento.",
        legislation_amending_act: "Relatório navegável com separação entre dispositivo alterador e dispositivos alterados.",
        manual_procedural: "Relatório navegável com índice procedural por títulos, seções e etapas internas.",
      }};
      document.getElementById("hero-title").textContent = data.metadata.file_name || "Arquivo";
      document.getElementById("hero-subtitle").textContent =
        subtitles[archetype] || "Relatório navegável gerado a partir dos artefatos estruturados do INDEX_ALL.";

      const heroMeta = document.getElementById("hero-meta");
      heroMeta.innerHTML = "";

      const pills = [
        data.metadata.file_type ? "Tipo: " + data.metadata.file_type : null,
        data.document_profile && data.document_profile.document_archetype
          ? "Arquétipo: " + data.document_profile.document_archetype
          : null,
        "Blocos: " + data.stats.block_count,
        "Entradas no índice: " + data.stats.index_entry_count,
      ].filter(Boolean);

      for (const label of pills) {{
        const span = document.createElement("span");
        span.className = "pill";
        span.textContent = label;
        heroMeta.appendChild(span);
      }}
    }}

    function renderStats() {{
      const statsRoot = document.getElementById("content-stats");
      statsRoot.innerHTML = "";

      const cards = [
        {{ label: "Blocos", value: data.stats.block_count }},
        {{ label: "Índice", value: data.stats.index_entry_count }},
        {{ label: "Filtrados", value: data.blocks.filter(matchesBlock).length }},
      ];

      for (const card of cards) {{
        const element = document.createElement("div");
        element.className = "stat-card";
        element.innerHTML = "<strong>" + escapeHtml(card.value) + "</strong><span class=\\"hint\\">" + escapeHtml(card.label) + "</span>";
        statsRoot.appendChild(element);
      }}
    }}

    function renderMetadata() {{
      const metadataGrid = document.getElementById("metadata-grid");
      const parserGrid = document.getElementById("parser-metadata-grid");
      const kindChips = document.getElementById("kind-chips");
      if (!metadataGrid || !parserGrid || !kindChips) {{
        return;
      }}
      metadataGrid.innerHTML = "";

      const items = [
        ["Nome", data.metadata.file_name],
        ["Tipo", data.metadata.file_type],
        ["Arquétipo documental", data.document_profile && data.document_profile.document_archetype],
        ["Domínio", data.document_profile && data.document_profile.domain],
        ["Estrutura principal", data.document_profile && data.document_profile.primary_structure],
        ["Tamanho", data.metadata.file_size_bytes != null ? data.metadata.file_size_bytes + " bytes" : null],
        ["Modificado em", data.metadata.modified_at],
        ["Origem", data.metadata.source_path],
      ].filter(([, value]) => value);

      for (const [label, value] of items) {{
        const card = document.createElement("div");
        card.className = "meta-item";
        card.innerHTML =
          "<span class=\\"meta-label\\">" + escapeHtml(label) + "</span>" +
          "<div class=\\"meta-value\\">" + escapeHtml(value) + "</div>";
        metadataGrid.appendChild(card);
      }}

      parserGrid.innerHTML = "";

      const parserEntries = Object.entries(data.parser_metadata || {{}});
      if (!parserEntries.length) {{
        parserGrid.innerHTML = "<div class=\\"empty-state\\">Sem metadados adicionais do parser.</div>";
      }} else {{
        for (const [label, value] of parserEntries) {{
          const card = document.createElement("div");
          card.className = "meta-item";
          card.innerHTML =
            "<span class=\\"meta-label\\">" + escapeHtml(label) + "</span>" +
            "<div class=\\"meta-value\\">" + escapeHtml(typeof value === "string" ? value : JSON.stringify(value)) + "</div>";
          parserGrid.appendChild(card);
        }}
      }}

      kindChips.innerHTML = "";
      for (const item of data.stats.kind_counts) {{
        const chip = document.createElement("span");
        chip.className = "badge";
        chip.textContent = item.label + ": " + item.count;
        kindChips.appendChild(chip);
      }}

    }}

    function renderSummary() {{
      const summaryRoot = document.getElementById("summary-text");
      if (!summaryRoot) {{
        return;
      }}
      summaryRoot.innerHTML = highlightText(data.summary || "Sem resumo disponível.");
    }}

    function renderSelectionContext() {{
      const selectedTitle = document.getElementById("selected-title");
      const selectedMeta = document.getElementById("selected-meta");
      const breadcrumbRoot = document.getElementById("selected-breadcrumb");
      const copyStructLinkButton = document.getElementById("copy-struct-link-button");
      const exportSelectedButton = document.getElementById("export-selected-button");
      const block = getSelectedBlock();

      if (!block) {{
        selectedTitle.textContent = "Nenhum trecho selecionado.";
        selectedMeta.textContent = "Escolha um item do índice ou um bloco do conteúdo.";
        breadcrumbRoot.innerHTML = "";
        copyStructLinkButton.disabled = true;
        exportSelectedButton.disabled = true;
        return;
      }}

      selectedTitle.innerHTML = highlightText(block.title || "Sem título");
      const metaParts = [block.kind_label, block.locator_text, block.position_text].filter(Boolean);
      selectedMeta.innerHTML = highlightText(metaParts.join(" | "));

      const parts = getBreadcrumbParts(block);
      breadcrumbRoot.innerHTML = parts
        .map((part) => "<span class=\\"crumb\\">" + highlightText(part) + "</span>")
        .join("");

      copyStructLinkButton.disabled = false;
      exportSelectedButton.disabled = false;
    }}

    function renderKindOptions() {{
      const select = document.getElementById("kind-filter");
      const existing = new Set(["all"]);
      for (const item of data.stats.kind_counts) {{
        if (existing.has(item.kind)) {{
          continue;
        }}
        existing.add(item.kind);
        const option = document.createElement("option");
        option.value = item.kind;
        option.textContent = item.label;
        select.appendChild(option);
      }}
    }}

    function renderTreeNode(node, depth) {{
      const wrapper = document.createElement("li");
      wrapper.className = "tree-node";

      const hasChildren = Boolean((node.children || []).length);
      const container = hasChildren ? document.createElement("details") : document.createElement("div");
      if (hasChildren) {{
        container.className = "tree-group";
        container.open = Boolean(state.query) || depth < 1 || nodeContainsSelected(node);
      }}

      const action = document.createElement("button");
      action.className = "tree-button" + (node.anchor === state.selectedAnchor ? " selected" : "");
      action.type = "button";
      action.innerHTML =
        "<div class=\\"tree-topline\\"><span class=\\"badge\\">" + escapeHtml(node.kind_label) + "</span></div>" +
        "<div class=\\"tree-title\\">" + highlightText(node.title || "Sem título") + "</div>" +
        (node.locator_text ? "<div class=\\"tree-locator\\">" + highlightText(node.locator_text) + "</div>" : "");
      action.addEventListener("click", () => selectAnchor(node.anchor));

      if (hasChildren) {{
        const summary = document.createElement("summary");
        summary.appendChild(action);
        container.appendChild(summary);

        const children = document.createElement("ul");
        children.className = "tree-children";
        for (const child of node.children) {{
          children.appendChild(renderTreeNode(child, depth + 1));
        }}
        container.appendChild(children);
      }} else {{
        container.appendChild(action);
      }}

      wrapper.appendChild(container);
      return wrapper;
    }}

    function renderTree() {{
      const treeRoot = document.getElementById("tree-root");
      treeRoot.innerHTML = "";

      const nodes = filterIndexNodes(data.index || []);
      if (!nodes.length) {{
        treeRoot.innerHTML = "<div class=\\"empty-state\\">Nenhum item do índice corresponde aos filtros atuais.</div>";
        return;
      }}

      const list = document.createElement("ul");
      list.className = "tree-root";
      for (const node of nodes) {{
        list.appendChild(renderTreeNode(node, 0));
      }}
      treeRoot.appendChild(list);
    }}

    function scrollSelectedTreeNodeIntoView() {{
      if (!state.selectedAnchor) {{
        return;
      }}
      const selectedTreeButton = document.querySelector(".tree-button.selected");
      if (selectedTreeButton) {{
        selectedTreeButton.scrollIntoView({{ block: "nearest" }});
      }}
    }}

    function buildReferenceText(block) {{
      const parts = [];
      if (data.metadata.file_name) {{
        parts.push(data.metadata.file_name);
      }}
      if (block.locator_text) {{
        parts.push(block.locator_text);
      }} else if (block.title) {{
        parts.push(block.title);
      }}
      if (block.position_text) {{
        parts.push(block.position_text);
      }}
      parts.push("#" + block.anchor);
      return parts.join(" | ");
    }}

    function fallbackCopyText(value) {{
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      textarea.style.pointerEvents = "none";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }}

    function slugify(value) {{
      const normalized = normalizeText(value).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
      return normalized || "trecho";
    }}

    async function copyReference(block) {{
      const reference = buildReferenceText(block);
      if (navigator.clipboard && window.isSecureContext) {{
        await navigator.clipboard.writeText(reference);
        return;
      }}
      fallbackCopyText(reference);
    }}

    async function copyStructuralLink(block) {{
      const link = buildStructuralLink(block);
      if (navigator.clipboard && window.isSecureContext) {{
        await navigator.clipboard.writeText(link);
        return;
      }}
      fallbackCopyText(link);
    }}

    function downloadTextFile(filename, content, mimeType) {{
      const blob = new Blob([content], {{ type: mimeType }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }}

    function exportSelectedBlock() {{
      const block = getSelectedBlock();
      if (!block) {{
        return;
      }}

      const reference = buildReferenceText(block);
      const structuralLink = buildStructuralLink(block);
      const markdown = [
        "# " + (block.title || "Trecho selecionado"),
        "",
        "- Arquivo: `" + (data.metadata.file_name || "") + "`",
        "- Tipo: `" + (block.kind_label || "") + "`",
        "- Referência: " + reference,
        "- Link estrutural: " + structuralLink,
        "",
        "```text",
        block.text || "",
        "```",
        "",
      ].join("\\n");

      const filename = slugify((block.title || block.anchor) + "-" + (data.metadata.file_stem || "trecho")) + ".md";
      downloadTextFile(filename, markdown, "text/markdown;charset=utf-8");
    }}

    function renderBlocks() {{
      const blockList = document.getElementById("block-list");
      blockList.innerHTML = "";

      const filteredBlocks = data.blocks.filter(matchesBlock);
      if (!filteredBlocks.length) {{
        blockList.innerHTML = "<div class=\\"empty-state\\">Nenhum bloco encontrado com os filtros atuais.</div>";
        return;
      }}

      for (const block of filteredBlocks) {{
        const card = document.createElement("article");
        card.className = "block-card" + (block.anchor === state.selectedAnchor ? " selected" : "");
        card.id = block.anchor;
        card.dataset.anchor = block.anchor;
        const copyLabel = state.copiedAnchor === block.anchor ? "Referência copiada" : "Copiar referência";
        card.innerHTML =
          "<div class=\\"block-header\\">" +
            "<div class=\\"block-title-group\\">" +
              "<div class=\\"badge\\">" + escapeHtml(block.kind_label) + "</div>" +
              "<div class=\\"block-title\\">" + highlightText(block.title || "Sem título") + "</div>" +
              ((block.locator_text || block.position_text)
                ? "<div class=\\"block-meta\\">" + highlightText([block.locator_text, block.position_text].filter(Boolean).join(" | ")) + "</div>"
                : "") +
            "</div>" +
            "<div class=\\"block-actions\\">" +
              "<button class=\\"copy-button" + (state.copiedAnchor === block.anchor ? " copied" : "") + "\\" type=\\"button\\" data-copy-anchor=\\"" + escapeHtml(block.anchor) + "\\">" + escapeHtml(copyLabel) + "</button>" +
              "<a class=\\"anchor-link\\" href=\\"#" + encodeURIComponent(block.anchor) + "\\">Âncora</a>" +
            "</div>" +
          "</div>" +
          "<pre class=\\"block-text\\">" + highlightText(block.text || "") + "</pre>";
        card.addEventListener("click", () => setSelected(block.anchor, false));
        const copyButton = card.querySelector("[data-copy-anchor]");
        if (copyButton) {{
          copyButton.addEventListener("click", async (event) => {{
            event.preventDefault();
            event.stopPropagation();
            try {{
              await copyReference(block);
              state.copiedAnchor = block.anchor;
              setSelected(block.anchor, false);
              window.setTimeout(() => {{
                if (state.copiedAnchor === block.anchor) {{
                  state.copiedAnchor = null;
                  renderBlocks();
                }}
              }}, 1800);
            }} catch (error) {{
              copyButton.textContent = "Falha ao copiar";
              window.setTimeout(() => {{
                renderBlocks();
              }}, 1800);
            }}
          }});
        }}
        blockList.appendChild(card);
      }}
    }}

    function setSelected(anchor, updateHash = true, hashValue = null) {{
      state.selectedAnchor = anchor || null;
      renderTree();
      renderBlocks();
      renderSelectionContext();
      scrollSelectedTreeNodeIntoView();

      if (updateHash && anchor) {{
        history.replaceState(null, "", hashValue || ("#" + anchor));
      }}
    }}

    function selectAnchor(anchor, hashValue = null) {{
      if (!anchor) {{
        return;
      }}

      const targetBlock = blocksByAnchor[anchor];
      if (!targetBlock) {{
        return;
      }}

      if (!matchesBlock(targetBlock)) {{
        state.query = "";
        state.kind = "all";
        document.getElementById("search-input").value = "";
        document.getElementById("kind-filter").value = "all";
        render();
      }}

      setSelected(anchor, true, hashValue);
      const element = document.getElementById(anchor);
      if (element) {{
        element.scrollIntoView({{ behavior: "smooth", block: "center" }});
      }}
    }}

    function render() {{
      renderStats();
      renderTree();
      renderBlocks();
      renderSummary();
      renderSelectionContext();
    }}

    function bindControls() {{
      document.getElementById("search-input").addEventListener("input", (event) => {{
        state.query = event.target.value;
        render();
      }});

      document.getElementById("kind-filter").addEventListener("change", (event) => {{
        state.kind = event.target.value;
        render();
      }});

      document.getElementById("copy-struct-link-button").addEventListener("click", async () => {{
        const block = getSelectedBlock();
        if (!block) {{
          return;
        }}
        const button = document.getElementById("copy-struct-link-button");
        const originalText = button.textContent;
        try {{
          await copyStructuralLink(block);
          button.textContent = "Link copiado";
          button.classList.add("copied");
        }} finally {{
          window.setTimeout(() => {{
            button.textContent = originalText;
            button.classList.remove("copied");
          }}, 1800);
        }}
      }});

      document.getElementById("export-selected-button").addEventListener("click", () => {{
        exportSelectedBlock();
      }});

      window.addEventListener("hashchange", () => {{
        const target = resolveHashTarget();
        if (target) {{
          selectAnchor(target.anchor, target.hashValue);
        }}
      }});
    }}

    function init() {{
      renderHero();
      renderMetadata();
      renderKindOptions();
      bindControls();

      const initialTarget = resolveHashTarget();
      state.selectedAnchor = (initialTarget && initialTarget.anchor) || (data.blocks[0] && data.blocks[0].anchor) || null;
      render();

      if (initialTarget) {{
        selectAnchor(initialTarget.anchor, initialTarget.hashValue);
      }}
    }}

    init();
  </script>
</body>
</html>
"""


def write_report_html(
    path: Path,
    metadata: dict,
    content: dict,
    index_entries: list[dict],
    summary: str,
) -> None:
    payload = _build_payload(metadata, content, index_entries, summary)
    path.write_text(_build_html(payload), encoding="utf-8")


def _collection_escape_html(value: object) -> str:
    text = str(value or "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_collection_tree(entries: list[dict]) -> str:
    if not entries:
        return "<p class=\"empty-state\">Sem entradas no índice mestre.</p>"

    def render_nodes(nodes: list[dict]) -> str:
        parts = ["<ul class=\"collection-tree\">"]
        for node in nodes:
            kind = _collection_escape_html(node.get("kind") or "entry")
            title = _collection_escape_html(node.get("title") or "Sem título")
            meta_bits = []
            if node.get("document_archetype"):
                meta_bits.append(f"arquétipo {_collection_escape_html(node['document_archetype'])}")
            if node.get("file_type"):
                meta_bits.append(f"tipo {_collection_escape_html(node['file_type'])}")
            if node.get("output_dir"):
                meta_bits.append(f"output {_collection_escape_html(node['output_dir'])}")
            meta_html = f"<div class=\"collection-node-meta\">{' | '.join(meta_bits)}</div>" if meta_bits else ""
            children = node.get("children") or []
            children_html = render_nodes(children) if children else ""
            parts.append(
                "<li>"
                f"<div class=\"collection-node\"><span class=\"badge\">{kind}</span> <strong>{title}</strong>{meta_html}</div>"
                f"{children_html}"
                "</li>"
            )
        parts.append("</ul>")
        return "".join(parts)

    return render_nodes(entries)


def write_collection_report_html(path: Path, collection_payload: dict) -> None:
    metadata = collection_payload.get("metadata", {})
    catalog = collection_payload.get("catalog", [])
    master_index = collection_payload.get("master_index", [])
    semantic = collection_payload.get("semantic", {})
    summary = collection_payload.get("summary", "")

    rows = []
    for entry in catalog:
        top_titles = " | ".join(_collection_escape_html(title) for title in entry.get("top_index_titles", [])[:6])
        rows.append(
            "<tr>"
            f"<td>{_collection_escape_html(entry.get('file_name'))}</td>"
            f"<td>{_collection_escape_html(entry.get('file_type'))}</td>"
            f"<td>{_collection_escape_html(entry.get('document_archetype'))}</td>"
            f"<td>{_collection_escape_html(entry.get('block_count'))}</td>"
            f"<td>{_collection_escape_html(entry.get('output_dir'))}</td>"
            f"<td>{top_titles}</td>"
            "</tr>"
        )

    file_type_counts = metadata.get("file_type_counts", {})
    archetype_counts = metadata.get("document_archetype_counts", {})
    search = semantic.get("search", {}) if isinstance(semantic, dict) else {}
    chunks = semantic.get("chunks", {}) if isinstance(semantic, dict) else {}
    retrieval_preview = semantic.get("retrieval_preview", {}) if isinstance(semantic, dict) else {}
    sample_chunk_list = "".join(
        f"<li>{_collection_escape_html(item)}</li>"
        for item in (chunks.get("sample_headings", []) or [])[:8]
    ) or "<li>Sem preview de chunks.</li>"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>INDEX_ALL Collection Report - {_collection_escape_html(metadata.get('collection_name', 'Acervo'))}</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: #f3f7fb;
      color: #0f172a;
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    .hero {{
      background: linear-gradient(135deg, #07306C, #046B91);
      color: white;
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 20px 48px rgba(7, 48, 108, 0.2);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 20px 0 24px;
    }}
    .card {{
      background: white;
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    }}
    .section {{
      background: white;
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
      margin-top: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #dbe3ee;
      text-align: left;
      vertical-align: top;
      padding: 10px 8px;
    }}
    th {{
      color: #07306C;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: #dbeafe;
      color: #07306C;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .collection-tree {{
      list-style: none;
      padding-left: 18px;
      margin: 10px 0 0;
    }}
    .collection-tree > li {{
      margin: 10px 0;
    }}
    .collection-node {{
      padding: 10px 12px;
      border-radius: 12px;
      background: #f8fbff;
      border: 1px solid #d8e7f7;
    }}
    .collection-node-meta {{
      color: #475569;
      font-size: 12px;
      margin-top: 6px;
    }}
    .metrics {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .metric {{
      background: #eef5ff;
      color: #07306C;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>INDEX_ALL Collection Report</h1>
      <p><strong>Coleção:</strong> {_collection_escape_html(metadata.get('collection_name', 'Acervo'))}</p>
      <p><strong>Origem:</strong> {_collection_escape_html(metadata.get('source_path', ''))}</p>
      <p>{_collection_escape_html(summary or 'Sem resumo consolidado disponível.')}</p>
    </section>

    <section class="cards">
      <div class="card"><strong>Arquivos</strong><div>{_collection_escape_html(metadata.get('file_count', 0))}</div></div>
      <div class="card"><strong>Blocos</strong><div>{_collection_escape_html(metadata.get('total_block_count', 0))}</div></div>
      <div class="card"><strong>Índice Mestre</strong><div>{_collection_escape_html(metadata.get('master_index_entry_count', 0))}</div></div>
      <div class="card"><strong>Search Index</strong><div>{_collection_escape_html(search.get('record_count', 0))}</div></div>
      <div class="card"><strong>Chunks</strong><div>{_collection_escape_html(chunks.get('chunk_count', 0))}</div></div>
    </section>

    <section class="section">
      <h2>Contagens Agregadas</h2>
      <div class="metrics">
        {''.join(f'<span class="metric">{_collection_escape_html(key)}: {_collection_escape_html(value)}</span>' for key, value in file_type_counts.items())}
      </div>
      <div class="metrics">
        {''.join(f'<span class="metric">{_collection_escape_html(key)}: {_collection_escape_html(value)}</span>' for key, value in archetype_counts.items())}
      </div>
    </section>

    <section class="section">
      <h2>Catálogo Do Acervo</h2>
      <table>
        <thead>
          <tr>
            <th>Arquivo</th>
            <th>Tipo</th>
            <th>Arquétipo</th>
            <th>Blocos</th>
            <th>Output Dir</th>
            <th>Principais Entradas</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows) if rows else '<tr><td colspan="6">Sem arquivos catalogados.</td></tr>'}
        </tbody>
      </table>
    </section>

    <section class="section">
      <h2>Índice Mestre Da Pasta</h2>
      {_render_collection_tree(list(master_index))}
    </section>

    <section class="section">
      <h2>Busca E Chunks</h2>
      <p><strong>Registros indexados para busca:</strong> {_collection_escape_html(search.get('record_count', 0))}</p>
      <p><strong>Chunks semânticos:</strong> {_collection_escape_html(chunks.get('chunk_count', 0))}</p>
      <p><strong>Filtros suportados:</strong> {_collection_escape_html(', '.join(search.get('supported_filters', []) or retrieval_preview.get('supported_filters', []) or []))}</p>
      <ul>
        {sample_chunk_list}
      </ul>
    </section>
  </div>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
