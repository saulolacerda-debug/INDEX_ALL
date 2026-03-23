# INDEX_ALL

INDEX_ALL e um motor universal de ingestao, estruturacao, indexacao, busca e sumarizacao de arquivos.
O objetivo do projeto e transformar arquivos heterogeneos em artefatos padronizados, pesquisaveis
e prontos para uso por humanos e por IA.

## Visao do produto

O projeto nasce como um nucleo generico para processar documentos e dados diversos, sem ficar preso
a um unico dominio. A especializacao tributaria, judicial, contabil ou societaria entra por cima do
core, sem contaminar a base.

Formatos suportados hoje:

- PDF
- DOCX
- XLSX
- PNG
- JPG/JPEG
- TIFF/TIF
- BMP
- WEBP
- XML
- HTML
- CSV
- TXT
- OFX

## Saidas do projeto

Para cada arquivo processado, o INDEX_ALL gera:

- `metadata.json`
- `content.json`
- `index.json`
- `ai_context.json`
- `ai_context.md`
- `summary.md`
- `report.html`

Quando a entrada e uma pasta, o INDEX_ALL tambem pode gerar artefatos de colecao:

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

Esses artefatos formam a base para:

- navegacao rapida do conteudo
- busca textual e retrieval hibrido local
- pipelines de RAG com grounding
- motores especialistas por dominio

## Arquitetura resumida

O sistema esta organizado em camadas:

1. Ingestao  
   Detecta o tipo do arquivo e roteia para o parser correto.

2. Estruturacao  
   Extrai conteudo, metadados, blocos e referencias navegaveis.

3. Indexacao e sumarizacao  
   Gera indice estrutural, payloads AI-ready e resumo executivo.

4. Semantica  
   Gera `search_index`, `chunks`, embeddings locais, `retrieval_preview`, `query_results` e `answer_results`.

5. Saida  
   Serializa os resultados em JSON, Markdown e HTML.

## Estrutura do projeto

```text
INDEX_ALL
|
|-- README.md
|-- AI_CONTEXT.md
|-- ARCHITECTURE.md
|-- ROADMAP.md
|-- PROMPTS.md
|-- requirements.txt
|-- pyproject.toml
|
|-- data
|   |-- raw
|   |-- processed
|   `-- samples
|
|-- docs
|   |-- PRD_MVP.md
|   |-- MANUTENCAO.md
|   |-- SCHEMA_UNIVERSAL.json
|   |-- decisions
|   |   `-- README.md
|   |-- diagrams
|   |   `-- README.md
|   `-- specs
|       `-- README.md
|
|-- scripts
|   |-- New-Batch.ps1
|   |-- Processar-Lote-Atual.ps1
|   |-- Run-Batch.ps1
|   `-- Query-Collection.ps1
|
|-- src
|   `-- index_all
|       |-- cli.py
|       |-- config.py
|       |-- main.py
|       |-- ingestion
|       |-- parsers
|       |-- indexing
|       |-- semantics
|       |-- outputs
|       `-- utils
|
|-- tests
`-- .github
    `-- workflows
```

## CLI principal

O comando principal do projeto agora e:

```text
index-all
```

O modo antigo continua compativel:

```text
python -m index_all.main
```

Os scripts `.ps1` continuam disponiveis como wrappers de conveniencia para lote e consulta.

## Como rodar

Crie e ative o ambiente virtual:

```powershell
cd C:\AI_PROJECTS\INDEX_ALL
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
cd /c/AI_PROJECTS/INDEX_ALL
python -m venv .venv
source .venv/bin/activate
```

Instale as dependencias e o pacote em modo editavel:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
```

Verifique a interface:

```powershell
index-all --help
python -m index_all.main --help
```

## OCR de imagens

O projeto processa imagens com OCR para:

- `png`
- `jpg`
- `jpeg`
- `tif`
- `tiff`
- `bmp`
- `webp`

Estrategia de OCR:

1. `Azure AI Vision READ` quando configurado
2. `RapidOCR` como fallback local
3. `Tesseract` como fallback adicional

Configuracao opcional por variaveis de ambiente:

```powershell
$env:INDEX_ALL_OCR_PROVIDER="auto"
$env:INDEX_ALL_OCR_LANGUAGE="pt,en"
$env:INDEX_ALL_AZURE_VISION_ENDPOINT="https://<seu-recurso>.cognitiveservices.azure.com/"
$env:INDEX_ALL_AZURE_VISION_KEY="<sua-chave>"
```

Se quiser forcar um motor especifico:

```powershell
$env:INDEX_ALL_OCR_PROVIDER="azure_vision"
```

ou

```powershell
$env:INDEX_ALL_OCR_PROVIDER="rapidocr"
```

ou

```powershell
$env:INDEX_ALL_OCR_PROVIDER="tesseract"
$env:INDEX_ALL_TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Azure OpenAI para answer generation

Configuracao opcional para completar o fluxo de RAG com resposta gerada:

```powershell
$env:INDEX_ALL_AZURE_OPENAI_ENDPOINT="https://<seu-recurso>.openai.azure.com/"
$env:INDEX_ALL_AZURE_OPENAI_API_KEY="<sua-chave>"
$env:INDEX_ALL_AZURE_OPENAI_DEPLOYMENT="<seu-deployment>"
```

Tambem sao aceitos os fallbacks:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`

## Processamento de arquivo ou pasta

Execute sobre um arquivo ou pasta:

```powershell
index-all "C:\AI_PROJECTS\INDEX_ALL\data\samples"
```

Ou, se preferir, mantenha a compatibilidade com:

```powershell
python -m index_all.main "C:\AI_PROJECTS\INDEX_ALL\data\samples"
```

## Fluxo mais simples para operar

Se voce quer copiar os arquivos e rodar um unico comando, use a pasta fixa:

```text
data\raw\entrada_atual
```

Fluxo:

1. Copie para `data\raw\entrada_atual` somente os arquivos do lote atual.
2. Rode:

```powershell
.\scripts\Processar-Lote-Atual.ps1 -Name clientes_marco
```

O script:

- cria um lote com timestamp dentro de `data\raw`
- move os arquivos de `entrada_atual` para esse lote
- processa o lote em `data\processed`
- deixa `entrada_atual` vazia e pronta para o proximo uso

Exemplo de resultado:

```text
data\raw\entrada_atual
data\raw\2026-03-15_201500_clientes_marco
data\processed\2026-03-15_201500_clientes_marco_collection
```

## Fluxo recomendado por lote

Para manter rastreabilidade, evitar mistura entre execucoes e permitir consultas futuras,
o fluxo recomendado e criar uma pasta nova para cada lote dentro de `data\raw`.

1. Crie um lote novo:

```powershell
.\scripts\New-Batch.ps1 -Name clientes_marco
```

2. Copie para essa pasta os arquivos que pertencem somente a esse lote.

3. Processe o lote com embeddings locais:

```powershell
.\scripts\Run-Batch.ps1 -BatchName 2026-03-15_101500_clientes_marco
```

4. Consulte a colecao depois, sem reprocessar:

```powershell
.\scripts\Query-Collection.ps1 -CollectionName 2026-03-15_101500_clientes_marco_collection -Query "nota cancelada"
```

5. Gere uma resposta grounded com Azure OpenAI:

```powershell
.\scripts\Query-Collection.ps1 `
  -CollectionName 2026-03-15_101500_clientes_marco_collection `
  -Query "quais dispositivos tratam do IBS?" `
  -Answer `
  -RankingProfile legal
```

6. Rode a CLI diretamente, se preferir:

```powershell
index-all .\data\processed\2026-03-15_101500_clientes_marco_collection `
  --query "quais regras de legalidade aparecem no documento?" `
  --answer `
  --ranking-profile legal `
  --limit 6
```

Observacoes:

- `Run-Batch.ps1` usa `--build-embeddings` por padrao. Use `-NoEmbeddings` se quiser somente busca textual.
- `Run-Batch.ps1` sem `-BatchName` pega o lote mais recente em `data\raw`.
- `Query-Collection.ps1` sem `-CollectionName` consulta a colecao mais recente em `data\processed`.
- `Query-Collection.ps1` e `Run-Batch.ps1` resolvem Python em `.venv\Scripts\python.exe`, depois `.venv/bin/python`, e por fim `python` no PATH.
- `index-all` e a interface principal; os scripts `.ps1` sao wrappers de conveniencia.
- A saida continua na mesma raiz `data\processed`, mas organizada por lote, preservando historico.

## Principios do projeto

- nucleo generico primeiro
- especializacoes depois
- schema universal de saida
- rastreabilidade do conteudo original
- simplicidade no MVP
- expansao preparada para IA e RAG
