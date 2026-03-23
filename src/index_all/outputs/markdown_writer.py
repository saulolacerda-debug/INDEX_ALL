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


def _append_catalog(lines: list[str], catalog_entries: list[dict]) -> None:
    if not catalog_entries:
        lines.extend(["- Sem arquivos catalogados.", ""])
        return

    for entry in catalog_entries:
        lines.append(
            f"- `{entry.get('file_name')}` | tipo `{entry.get('file_type')}` | "
            f"arquétipo `{entry.get('document_archetype')}` | blocos `{entry.get('block_count', 0)}`"
        )
        top_titles = entry.get("top_index_titles", []) or []
        if top_titles:
            lines.append(f"  Principais entradas: {' | '.join(top_titles[:6])}")
        if entry.get("output_dir"):
            lines.append(f"  Output: `{entry['output_dir']}`")
    lines.append("")


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


def write_collection_summary_markdown(path: Path, collection_payload: dict) -> None:
    metadata = collection_payload.get("metadata", {})
    catalog = collection_payload.get("catalog", [])
    master_index = collection_payload.get("master_index", [])
    semantic = collection_payload.get("semantic", {})
    summary = collection_payload.get("summary", "")

    lines = [
        f"# Coleção - {metadata.get('collection_name', 'Acervo')}",
        "",
        "> Artefato consolidado do lote processado pelo INDEX_ALL.",
        "",
        "## Metadados Agregados",
        "",
        f"- Nome da coleção: `{metadata.get('collection_name', '')}`",
        f"- Origem: `{metadata.get('source_path', '')}`",
        f"- Arquivos: `{metadata.get('file_count', 0)}`",
        f"- Blocos totais: `{metadata.get('total_block_count', 0)}`",
        f"- Entradas no índice mestre: `{metadata.get('master_index_entry_count', 0)}`",
        "",
    ]

    file_type_counts = metadata.get("file_type_counts", {})
    if file_type_counts:
        lines.extend(["## Arquivos Por Tipo", ""])
        lines.extend(f"- `{file_type}`: `{count}`" for file_type, count in file_type_counts.items())
        lines.append("")

    archetype_counts = metadata.get("document_archetype_counts", {})
    if archetype_counts:
        lines.extend(["## Arquivos Por Arquétipo", ""])
        lines.extend(f"- `{archetype}`: `{count}`" for archetype, count in archetype_counts.items())
        lines.append("")

    _append_list_section(
        lines,
        "## Principais Títulos Encontrados",
        [f"`{title}`" for title in metadata.get("top_titles", [])],
    )
    _append_list_section(
        lines,
        "## Arquivos Com Estrutura Normativa",
        [f"`{name}`" for name in metadata.get("files_with_normative_structure", [])],
    )
    _append_list_section(
        lines,
        "## Arquivos Com Estrutura Procedural",
        [f"`{name}`" for name in metadata.get("files_with_procedural_structure", [])],
    )

    if semantic:
        lines.extend(["## Busca E Chunks", ""])
        search = semantic.get("search", {})
        chunks = semantic.get("chunks", {})
        embeddings = semantic.get("embeddings", {})
        retrieval_preview = semantic.get("retrieval_preview", {})
        query_results = semantic.get("query_results", {})
        answer_results = semantic.get("answer_results", {})
        if search:
            lines.append(f"- Registros no search index: `{search.get('record_count', 0)}`")
            raw_record_count = search.get("raw_record_count")
            if raw_record_count:
                lines.append(f"- Registros brutos antes da deduplicação: `{raw_record_count}`")
            duplicates_removed = (search.get("exact_duplicates_removed", 0) or 0) + (search.get("near_duplicates_removed", 0) or 0)
            if duplicates_removed:
                lines.append(f"- Duplicatas removidas: `{duplicates_removed}`")
            supported_filters = search.get("supported_filters", []) or []
            if supported_filters:
                lines.append(f"- Filtros suportados: `{', '.join(supported_filters)}`")
        if chunks:
            lines.append(f"- Chunks gerados: `{chunks.get('chunk_count', 0)}`")
            chunk_metadata = chunks.get("metadata", {}) or {}
            embedding_count = chunk_metadata.get("embedding_count")
            if embedding_count is not None:
                lines.append(f"- Chunks com embedding persistido: `{embedding_count}`")
            sample_headings = chunks.get("sample_headings", []) or []
            if sample_headings:
                lines.append(f"- Primeiros chunks: `{' | '.join(sample_headings[:5])}`")
        if embeddings:
            lines.append(f"- Embeddings persistidos: `{embeddings.get('embedding_count', 0)}`")
            if embeddings.get("embedding_state"):
                lines.append(f"- Estado do índice vetorial: `{embeddings.get('embedding_state')}`")
            if embeddings.get("vector_size"):
                lines.append(f"- Dimensão vetorial local: `{embeddings.get('vector_size')}`")
            if embeddings.get("embedding_algorithm"):
                lines.append(f"- Algoritmo de embedding: `{embeddings.get('embedding_algorithm')}`")
        if retrieval_preview:
            lines.append(f"- Modo de retrieval: `{retrieval_preview.get('mode', 'textual_retrieval_ready')}`")
            if retrieval_preview.get("ranking_profile"):
                lines.append(f"- Perfil de ranking do preview: `{retrieval_preview.get('ranking_profile')}`")
            preview_queries = retrieval_preview.get("preview_queries", []) or []
            if preview_queries:
                lines.append(f"- Queries de preview: `{' | '.join(preview_queries[:5])}`")
        sample_chunks = retrieval_preview.get("sample_chunks", []) or []
        if sample_chunks:
            lines.append("- Preview de retrieval:")
            for chunk in sample_chunks[:3]:
                parts = [
                    str(chunk.get("file_name") or ""),
                    str(chunk.get("document_archetype") or ""),
                    str(chunk.get("heading_path_text") or ""),
                    f"score={chunk.get('score', 0)}",
                    f"text={chunk.get('text_score', 0)}",
                    f"vector={chunk.get('vector_score', 0)}",
                    str(chunk.get("retrieval_mode") or ""),
                ]
                if chunk.get("locator_path"):
                    parts.append(str(chunk["locator_path"]))
                lines.append(f"  {' | '.join(part for part in parts if part)}")
        sample_queries = retrieval_preview.get("sample_queries", []) or []
        if sample_queries:
            lines.append("- Preview por query:")
            for preview in sample_queries[:3]:
                query = str(preview.get("query") or "")
                lines.append(f"  query=`{query}`")
                for item in (preview.get("results", []) or [])[:2]:
                    parts = [
                        str(item.get("file_name") or ""),
                        str(item.get("document_archetype") or ""),
                        str(item.get("heading_path_text") or ""),
                        f"score={item.get('score', 0)}",
                    ]
                    if item.get("locator_path"):
                        parts.append(str(item["locator_path"]))
                    lines.append(f"    {' | '.join(part for part in parts if part)}")
        if query_results:
            lines.append(f"- Última consulta: `{query_results.get('query', '')}`")
            lines.append(f"- Hits retornados: `{query_results.get('total_hits', 0)}`")
            if query_results.get("ranking_profile"):
                lines.append(f"- Perfil de ranking da consulta: `{query_results.get('ranking_profile')}`")
            if query_results.get("results"):
                lines.append("- Preview dos resultados da consulta:")
                for item in (query_results.get("results", []) or [])[:3]:
                    parts = [
                        str(item.get("file_name") or ""),
                        str(item.get("document_archetype") or ""),
                        str(item.get("heading_path_text") or ""),
                        f"score={item.get('score', 0)}",
                    ]
                    if item.get("locator_path"):
                        parts.append(str(item["locator_path"]))
                    lines.append(f"  {' | '.join(part for part in parts if part)}")
        if answer_results:
            lines.append(f"- Última resposta: status `{answer_results.get('status', 'unknown')}`")
            if answer_results.get("query"):
                lines.append(f"- Pergunta respondida: `{answer_results.get('query', '')}`")
            if answer_results.get("ranking_profile"):
                lines.append(f"- Perfil de ranking da resposta: `{answer_results.get('ranking_profile')}`")
            if answer_results.get("provider"):
                lines.append(f"- Provider: `{answer_results.get('provider')}`")
            if answer_results.get("deployment"):
                lines.append(f"- Deployment: `{answer_results.get('deployment')}`")
            if answer_results.get("citation_count") is not None:
                lines.append(f"- Citações usadas: `{answer_results.get('citation_count', 0)}`")
            if answer_results.get("answer_preview"):
                lines.append(f"- Preview da resposta: `{answer_results.get('answer_preview')}`")
            citations = answer_results.get("citations", []) or []
            if citations:
                lines.append("- Citações da resposta:")
                for item in citations[:3]:
                    lines.append(f"  [{item.get('id')}] {item.get('reference')}")
        lines.append("")

    lines.extend(["## Resumo Consolidado", "", summary or "Sem resumo consolidado disponível.", ""])
    lines.extend(["## Catálogo Do Acervo", ""])
    _append_catalog(lines, list(catalog))

    lines.extend(["## Índice Mestre", ""])
    if master_index:
        _append_index_entries(lines, list(master_index))
    else:
        lines.append("- Sem entradas no índice mestre.")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_answer_results_markdown(path: Path, answer_payload: dict) -> None:
    citations = list(answer_payload.get("citations", []) or [])
    grounding = list(answer_payload.get("grounding", []) or [])
    filters = dict(answer_payload.get("filters", {}) or {})

    lines = [
        f'# Resposta - "{answer_payload.get("query", "")}"',
        "",
        f"- Status: `{answer_payload.get('status', 'unknown')}`",
        f"- Modo de retrieval: `{answer_payload.get('mode', 'textual')}`",
        f"- Perfil de ranking: `{answer_payload.get('ranking_profile', 'legal')}`",
        f"- Provider: `{answer_payload.get('provider', 'azure_openai')}`",
        f"- Deployment: `{answer_payload.get('deployment', '')}`",
    ]
    if answer_payload.get("response_id"):
        lines.append(f"- Response ID: `{answer_payload.get('response_id')}`")
    if filters:
        lines.append(
            "- Filtros: "
            + ", ".join(f"`{key}={value}`" for key, value in filters.items() if value not in (None, "", []))
        )
    lines.append("")

    answer_markdown = str(answer_payload.get("answer_markdown") or "").strip()
    answer_text = str(answer_payload.get("answer_text") or "").strip()
    if answer_markdown:
        lines.extend(["## Resposta", "", answer_markdown, ""])
    elif answer_text:
        lines.extend(["## Diagnóstico", "", answer_text, ""])

    if citations:
        lines.extend(["## Citações", ""])
        for item in citations:
            lines.append(f"- [{item.get('id')}] {item.get('reference')}")
        lines.append("")

    if grounding:
        lines.extend(["## Grounding Utilizado", ""])
        for item in grounding:
            parts = [
                f"[{item.get('id')}]",
                str(item.get("reference") or ""),
                f"score={item.get('score', 0)}",
                str(item.get("retrieval_mode") or ""),
            ]
            lines.append(f"- {' | '.join(part for part in parts if part)}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
