# INDEX_ALL

INDEX_ALL é um motor universal de ingestão, estruturação, indexação e sumarização de arquivos.
O objetivo do projeto é transformar arquivos heterogêneos do dia a dia em saídas padronizadas,
pesquisáveis e prontas para uso por humanos e por IA.

## Visão do produto

O projeto nasce como um núcleo genérico para processar documentos e dados diversos, sem ficar
preso a um único domínio. A especialização tributária, judicial, contábil ou societária será
feita depois, por camadas ou plugins sobre o núcleo base.

Arquivos-alvo do núcleo atual:

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

## Saídas do MVP

Para cada arquivo processado, o INDEX_ALL gera:

- `metadata.json`
- `content.json`
- `index.json`
- `summary.md`

Esses artefatos formam a base para:

- navegação rápida do conteúdo
- busca textual e semântica futura
- pipelines de RAG
- motores especialistas (tributário, judicial, contábil)

## Arquitetura resumida

O sistema foi desenhado em camadas:

1. Ingestão  
   Detecta o tipo do arquivo e roteia para o parser correto.

2. Estruturação  
   Extrai conteúdo, metadados, blocos e referências navegáveis.

3. Indexação e sumarização  
   Gera índice estrutural e resumo executivo.

4. Saída  
   Serializa os resultados em JSON e Markdown.

## Estrutura do projeto

```text
INDEX_ALL
│
├── README.md
├── AI_CONTEXT.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── PROMPTS.md
├── requirements.txt
├── pyproject.toml
│
├── data
│   ├── raw
│   ├── processed
│   └── samples
│
├── docs
│   ├── PRD_MVP.md
│   ├── SCHEMA_UNIVERSAL.json
│   ├── decisions
│   ├── diagrams
│   └── specs
│
├── scripts
│   ├── New-Batch.ps1
│   ├── Processar-Lote-Atual.ps1
│   ├── Run-Batch.ps1
│   └── Query-Collection.ps1
│
├── src
│   └── index_all
│       ├── config.py
│       ├── main.py
│       ├── ingestion
│       ├── parsers
│       ├── indexing
│       ├── semantics
│       ├── outputs
│       └── utils
│
└── tests
```

## Como rodar

Crie e ative o ambiente virtual:

```powershell
cd C:\AI_PROJECTS\INDEX_ALL
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Instale as dependências e o pacote em modo editável:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
```

## OCR de imagens

O projeto agora processa imagens com OCR nativo para:

- `png`
- `jpg`
- `jpeg`
- `tif`
- `tiff`
- `bmp`
- `webp`

Estratégia de OCR:

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

Execute sobre um arquivo ou pasta:

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

O script cria uma pasta como:

```text
data\raw\2026-03-15_101500_clientes_marco
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

Observacoes:

- `Run-Batch.ps1` usa `--build-embeddings` por padrao. Use `-NoEmbeddings` se quiser somente busca textual.
- `Run-Batch.ps1` sem `-BatchName` pega o lote mais recente em `data\raw`.
- `Query-Collection.ps1` sem `-CollectionName` consulta a colecao mais recente em `data\processed`.
- A saida continua na mesma raiz `data\processed`, mas organizada por lote, preservando historico.

## Exemplo de resultado

```text
data\processed\meu_arquivo
├── metadata.json
├── content.json
├── index.json
└── summary.md
```

## Princípios do projeto

- núcleo genérico primeiro
- especializações depois
- schema universal de saída
- rastreabilidade do conteúdo original
- simplicidade no MVP
- expansão preparada para IA e RAG
