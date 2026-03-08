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

Execute sobre um arquivo ou pasta:

```powershell
python -m index_all.main "C:\AI_PROJECTS\INDEX_ALL\data\samples"
```

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
