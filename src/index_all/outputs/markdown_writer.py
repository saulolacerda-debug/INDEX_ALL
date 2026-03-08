from __future__ import annotations

from pathlib import Path


def _append_index_entries(lines: list[str], entries: list[dict], depth: int = 0) -> None:
    for entry in entries:
        indent = "  " * depth
        lines.append(f"{indent}- [{entry.get('kind')}] {entry.get('title')}")
        children = entry.get("children") or []
        if children:
            _append_index_entries(lines, children, depth + 1)


def _append_list_section(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend([title, ""])
    if not items:
        lines.append("- Sem itens.")
        lines.append("")
        return
    lines.extend(f"- {item}" for item in items)
    lines.append("")


def _append_block(lines: list[str], block: dict) -> None:
    block_id = block.get("id", "block_sem_id")
    display_title = block.get("display_title") or block.get("title") or block_id
    text = str(block.get("text") or "")
    extra = block.get("extra", {}) or {}
    hierarchy_path = block.get("hierarchy_path") or []

    lines.extend([f"### [{block_id}] {display_title}", ""])
    lines.append(f"- Tipo: `{block.get('kind', 'unknown')}`")
    lines.append(f"- Referência de citação: `{block.get('source_reference', block_id)}`")
    if hierarchy_path:
        lines.append(f"- Caminho estrutural: `{' > '.join(hierarchy_path)}`")
    if block.get("position_text"):
        lines.append(f"- Posição: `{block['position_text']}`")
    if extra.get("summary"):
        lines.append(f"- Resumo curto: `{extra['summary']}`")
    lines.extend(["", "Texto fonte:", "", "```text", text, "```", "", "---", ""])


def write_ai_context_markdown(path: Path, ai_context_payload: dict) -> None:
    metadata = ai_context_payload.get("metadata", {})
    document_profile = ai_context_payload.get("document_profile", {})
    ai_ready = ai_context_payload.get("ai_ready", {})
    consultation_hints = ai_context_payload.get("consultation_hints", {})
    parser_metadata = ai_context_payload.get("parser_metadata", {})
    index_entries = ai_context_payload.get("index", [])
    blocks = ai_context_payload.get("blocks", [])
    summary = ai_context_payload.get("summary", "")

    lines = [
        f"# AI Context - {metadata.get('file_name', 'Arquivo')}",
        "",
        "> Artefato textual único recomendado para upload em IA quando o modelo responder melhor a Markdown do que JSON.",
        "",
        "## Como Usar Com IA",
        "",
        "- Este arquivo foi preparado para consulta, parecer, análise, diagnóstico e resposta fundamentada.",
        "- Use o índice para localizar a parte relevante antes de interpretar o texto.",
        "- Fundamente a resposta nos blocos de `Texto fonte` e cite a `Referência de citação`.",
        "- Se a conclusão depender de mais de um trecho, cite cada bloco usado.",
        "- Não trate resumos curtos como substitutos do texto-fonte.",
        "",
        "## Diretriz De Uso",
        "",
        f"- Artefato preferencial para upload textual: `ai_context.md`",
        f"- Artefato preferencial para upload JSON: `{ai_ready.get('preferred_artifact_for_upload', 'ai_context.json')}`",
        f"- Template de citação: `{consultation_hints.get('citation_template', '{source_reference}')}`",
        "",
        "## Metadados",
        "",
        f"- Nome: `{metadata.get('file_name', '')}`",
        f"- Tipo: `{metadata.get('file_type', '')}`",
        f"- Tamanho (bytes): `{metadata.get('file_size_bytes', 0)}`",
        f"- Modificado em: `{metadata.get('modified_at', '')}`",
        f"- Origem: `{metadata.get('source_path', '')}`",
        "",
        "## Perfil Do Documento",
        "",
        f"- Domínio: `{document_profile.get('domain', 'unknown')}`",
        f"- Arquétipo documental: `{document_profile.get('document_archetype', 'unknown')}`",
        f"- Estrutura principal: `{document_profile.get('primary_structure', 'unknown')}`",
        f"- Blocos: `{document_profile.get('block_count', 0)}`",
        f"- Entradas no índice: `{document_profile.get('index_entry_count', 0)}`",
        f"- Objetivo de consulta: `{document_profile.get('consultation_goal', '')}`",
        "",
    ]

    structure_counts = document_profile.get("structure_counts", {})
    if structure_counts:
        lines.extend(["## Estrutura Identificada", ""])
        lines.extend(f"- `{kind}`: `{count}`" for kind, count in structure_counts.items())
        lines.append("")

    parser_items = [f"`{key}`: `{value}`" for key, value in parser_metadata.items()]
    _append_list_section(lines, "## Metadados Do Parser", parser_items)
    _append_list_section(lines, "## Workflow Recomendado Para IA", consultation_hints.get("recommended_workflow", []))
    _append_list_section(lines, "## Regras De Resposta", consultation_hints.get("answering_rules", []))

    top_level_titles = [f"`{title}`" for title in consultation_hints.get("top_level_index_titles", [])]
    _append_list_section(lines, "## Entradas De Alto Nível", top_level_titles)

    lines.extend(["## Índice Hierárquico Completo", ""])
    if index_entries:
        _append_index_entries(lines, index_entries)
    else:
        lines.append("- Sem entradas estruturadas.")
    lines.append("")

    lines.extend(["## Resumo Analítico", "", summary or "Sem resumo disponível.", ""])

    lines.extend(["## Blocos Estruturados", ""])
    for block in blocks:
        _append_block(lines, block)

    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary_markdown(path: Path, consultation_payload: dict) -> None:
    metadata = consultation_payload.get("metadata", {})
    document_profile = consultation_payload.get("document_profile", {})
    ai_ready = consultation_payload.get("ai_ready", {})
    parser_metadata = consultation_payload.get("parser_metadata", {})
    index_entries = consultation_payload.get("index", [])
    blocks = consultation_payload.get("blocks", [])
    summary = consultation_payload.get("summary", "")

    lines = [
        f"# {metadata.get('file_name', 'Arquivo')}",
        "",
        "> Artefato autocontido para consulta por IA. Para upload único em JSON, prefira `ai_context.json`; para upload único em Markdown, prefira `ai_context.md`; este arquivo é a versão de revisão humana + IA.",
        "",
        "## Como Usar Com IA",
        "",
        "- Se for enviar apenas um artefato JSON para a IA, use `ai_context.json`.",
        "- Se for enviar apenas um artefato Markdown para a IA, use `ai_context.md`.",
        "- Use o índice hierárquico para localizar rapidamente o dispositivo ou seção pertinente.",
        "- Cite a fonte usando `Referência de citação` e, quando útil, o `block id`.",
        "- Para pareceres, análises e diagnósticos, fundamente a resposta no bloco-fonte e não apenas no resumo.",
        "- Quando a conclusão depender de mais de um trecho, combine os blocos citando cada referência separadamente.",
        "",
        "## Metadados",
        "",
        f"- Nome: `{metadata.get('file_name', '')}`",
        f"- Tipo: `{metadata.get('file_type', '')}`",
        f"- Tamanho (bytes): `{metadata.get('file_size_bytes', 0)}`",
        f"- Modificado em: `{metadata.get('modified_at', '')}`",
        f"- Origem: `{metadata.get('source_path', '')}`",
        "",
        "## Perfil Do Documento",
        "",
        f"- Domínio: `{document_profile.get('domain', 'unknown')}`",
        f"- Arquétipo documental: `{document_profile.get('document_archetype', 'unknown')}`",
        f"- Estrutura principal: `{document_profile.get('primary_structure', 'unknown')}`",
        f"- Blocos: `{document_profile.get('block_count', 0)}`",
        f"- Entradas no índice: `{document_profile.get('index_entry_count', 0)}`",
        f"- Objetivo de consulta: `{document_profile.get('consultation_goal', '')}`",
        "",
    ]

    structure_counts = document_profile.get("structure_counts", {})
    if structure_counts:
        lines.extend(["## Estrutura Identificada", ""])
        lines.extend(f"- `{kind}`: `{count}`" for kind, count in structure_counts.items())
        lines.append("")

    parser_items = [f"`{key}`: `{value}`" for key, value in parser_metadata.items()]
    _append_list_section(lines, "## Metadados Do Parser", parser_items)
    _append_list_section(lines, "## Workflow Recomendado Para IA", ai_ready.get("recommended_workflow", []))
    _append_list_section(lines, "## Regras De Resposta", ai_ready.get("answering_rules", []))

    lines.extend(["## Índice Hierárquico Completo", ""])
    if index_entries:
        _append_index_entries(lines, index_entries)
    else:
        lines.append("- Sem entradas estruturadas.")
    lines.append("")

    lines.extend(["## Resumo Analítico", "", summary or "Sem resumo disponível.", ""])

    lines.extend(["## Blocos Estruturados", ""])
    for block in blocks:
        _append_block(lines, block)

    path.write_text("\n".join(lines), encoding="utf-8")
