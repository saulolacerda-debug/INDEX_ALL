# ARCHITECTURE.md

## Visao geral

O INDEX_ALL e um motor universal de processamento de arquivos. A arquitetura foi desenhada para
receber formatos diferentes, convertelos para uma estrutura comum, gerar artefatos de arquivo
e, quando a entrada e uma pasta, consolidar busca e retrieval sobre a colecao.

## Pipeline principal

```text
Entrada -> Deteccao do tipo -> Parser -> Normalizacao -> Indexacao -> Resumo -> Semantica -> Escrita de saida
```

## Camadas

### 1. Ingestao

Responsabilidade:
- receber um arquivo ou uma pasta
- identificar o tipo do arquivo
- encaminhar para o parser adequado

Modulo principal:
- `src/index_all/ingestion/file_router.py`

### 2. Parsers

Responsabilidade:
- extrair o conteudo bruto do arquivo
- transformar o conteudo em blocos estruturados
- preservar metadados especificos do formato

Parsers principais:
- `pdf_parser.py`
- `docx_parser.py`
- `xlsx_parser.py`
- `xml_parser.py`
- `html_parser.py`
- `csv_parser.py`
- `txt_parser.py`
- `ofx_parser.py`
- `image_parser.py`

### 3. Indexacao

Responsabilidade:
- extrair metadados comuns
- montar indice navegavel
- gerar resumo executivo
- enriquecer o documento com payloads AI-ready

Modulos principais:
- `metadata_extractor.py`
- `structure_indexer.py`
- `summary_builder.py`
- `consultation_payload.py`
- `catalog_builder.py`
- `master_index_builder.py`

### 4. Semantica

Responsabilidade:
- suportar busca textual
- gerar chunks para retrieval
- persistir embeddings locais
- combinar sinal textual e vetorial com reranking
- gerar `retrieval_preview`, `query_results` e `answer_results`

Modulos principais:
- `search_engine.py`
- `chunker.py`
- `embedding_store.py`
- `retrieval.py`
- `reranker.py`
- `query_interface.py`
- `answering.py`

### 5. Saida

Responsabilidade:
- escrever artefatos finais
- manter formato consistente por arquivo e por colecao

Modulos principais:
- `json_writer.py`
- `markdown_writer.py`
- `html_writer.py`

## Schema universal

O coracao do sistema e um schema comum. Cada parser pode ter detalhes proprios, mas deve convergir
para esta forma logica:

```json
{
  "metadata": {
    "file_name": "",
    "file_type": "",
    "file_size_bytes": 0,
    "modified_at": "",
    "source_path": ""
  },
  "content": {
    "blocks": [],
    "parser_metadata": {}
  },
  "index": [],
  "summary": ""
}
```

## Estrutura dos blocos

Os parsers produzem blocos de conteudo com estrutura semelhante a esta:

```json
{
  "id": "block_0001",
  "kind": "paragraph",
  "title": null,
  "text": "conteudo extraido",
  "locator": {
    "page": 1,
    "sheet": null,
    "line_start": null,
    "line_end": null
  },
  "extra": {}
}
```

## Artefatos por arquivo

Cada arquivo processado gera:

- `metadata.json`
- `content.json`
- `index.json`
- `ai_context.json`
- `ai_context.md`
- `summary.md`
- `report.html`

## Artefatos por colecao

Quando a entrada e uma pasta, o projeto pode gerar:

- `catalog.json`
- `master_index.json`
- `collection_metadata.json`
- `collection_summary.md`
- `collection_report.html`
- `search_index.json`
- `chunks.json`
- `embeddings_index.json`
- `retrieval_preview.json`
- `query_results.json`
- `answer_results.json`
- `answer_results.md`

## Regras arquiteturais

1. O core nao pode depender de uma logica tematica unica.
2. Parsers nao devem escrever arquivos diretamente.
3. Saidas devem ser responsabilidade da camada `outputs`.
4. Indexacao deve depender do schema produzido pelos parsers.
5. Semantica deve operar sobre artefatos processados e nao sobre parser side effects.
6. Especializacoes futuras devem entrar por extensao, nao por contaminacao do core.

## Organizacao por dominio futuro

Quando o nucleo estiver estabilizado, a evolucao correta continua sendo por packs tematicos:

- `tax_pack`
- `judicial_pack`
- `accounting_pack`
- `corporate_pack`

Esses modulos poderao:
- classificar entidades especificas
- extrair campos especializados
- aplicar taxonomias proprias
- gerar relatorios tematicos

## Fluxo operacional atual

### Entrada
- arquivo unico
- ou pasta com multiplos arquivos
- ou uma colecao ja processada para consulta

### Processamento por arquivo
1. detectar extensao
2. chamar parser
3. extrair metadados comuns
4. montar indice
5. gerar resumo
6. escrever artefatos do arquivo

### Consolidacao por colecao
1. construir catalogo
2. construir indice mestre
3. gerar search index
4. gerar chunks
5. persistir embeddings locais quando solicitado
6. gerar previews e artefatos de consulta/resposta

### Resultado
Um diretorio por arquivo processado em `data/processed` e, para entradas em pasta, um diretorio
de colecao com os artefatos consolidados.

## Criterio de sucesso da base atual

A base atual e considerada valida quando:

- processa os tipos suportados com falha controlada
- gera artefatos consistentes por arquivo
- gera artefatos consolidados por colecao
- suporta busca textual, retrieval hibrido e answer generation grounded
- preserva compatibilidade com `python -m index_all.main` e com a CLI `index-all`
