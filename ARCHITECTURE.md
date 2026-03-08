# ARCHITECTURE.md

## Visão geral

O INDEX_ALL é um motor universal de processamento de arquivos. A arquitetura foi desenhada para
receber formatos diferentes, convertê-los para uma estrutura comum e gerar artefatos de saída
padronizados.

## Pipeline principal

```text
Entrada -> Detecção do tipo -> Parser -> Normalização -> Indexação -> Resumo -> Escrita de saída
```

## Camadas

### 1. Ingestão

Responsabilidade:
- receber um arquivo ou uma pasta
- identificar o tipo do arquivo
- encaminhar para o parser adequado

Módulo principal:
- `src/index_all/ingestion/file_router.py`

### 2. Parsers

Responsabilidade:
- extrair o conteúdo bruto do arquivo
- transformar o conteúdo em blocos estruturados
- preservar metadados específicos do formato

Parsers previstos:
- `pdf_parser.py`
- `docx_parser.py`
- `xlsx_parser.py`
- `xml_parser.py`
- `html_parser.py`
- `csv_parser.py`
- `txt_parser.py`
- `ofx_parser.py`

### 3. Indexação

Responsabilidade:
- extrair metadados comuns
- montar índice navegável
- gerar resumo executivo inicial

Módulos:
- `metadata_extractor.py`
- `structure_indexer.py`
- `summary_builder.py`

### 4. Saída

Responsabilidade:
- escrever artefatos finais
- manter formato consistente por arquivo processado

Módulos:
- `json_writer.py`
- `markdown_writer.py`

### 5. Semântica

Responsabilidade:
- futuramente suportar busca textual e semântica
- preparar integração com embeddings e RAG

Módulo inicial:
- `search_engine.py`

## Schema universal

O coração do sistema é um schema comum. Cada parser pode ter detalhes próprios, mas deve convergir
para esta forma lógica:

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

Os parsers devem produzir blocos de conteúdo com estrutura semelhante a esta:

```json
{
  "id": "block_0001",
  "kind": "paragraph",
  "title": null,
  "text": "conteúdo extraído",
  "locator": {
    "page": 1,
    "sheet": null,
    "line_start": null,
    "line_end": null
  },
  "extra": {}
}
```

## Regras arquiteturais

1. O core não pode depender de uma lógica temática específica.
2. Parsers não devem escrever arquivos diretamente.
3. Saídas devem ser responsabilidade da camada `outputs`.
4. Indexação deve depender do schema produzido pelos parsers.
5. Especializações futuras devem entrar por extensão, não por contaminação do core.

## Organização por domínio futuro

Quando o núcleo estiver estabilizado, a evolução correta será por packs temáticos:

- `tax_pack`
- `judicial_pack`
- `accounting_pack`
- `corporate_pack`

Esses módulos poderão:
- classificar entidades específicas
- extrair campos especializados
- aplicar taxonomias próprias
- gerar relatórios temáticos

## Fluxo do MVP

### Entrada
- arquivo único
- ou pasta com múltiplos arquivos

### Processamento por arquivo
1. detectar extensão
2. chamar parser
3. extrair metadados comuns
4. montar índice
5. gerar resumo
6. escrever `metadata.json`, `content.json`, `index.json`, `summary.md`

### Resultado
Um diretório por arquivo processado em `data/processed`.

## Critério de sucesso do MVP

O MVP é considerado válido quando:
- processa ao menos um arquivo de cada tipo suportado
- gera os quatro artefatos padrão
- mantém estrutura consistente
- falha de modo controlado quando o parser não consegue extrair tudo
