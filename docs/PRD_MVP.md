# PRD_MVP.md

## Problema
Arquivos heterogêneos do dia a dia são difíceis de navegar, resumir e reutilizar de forma padronizada.

## Solução
Criar um núcleo local em Python para ingerir, estruturar, indexar e resumir múltiplos formatos de arquivo.

## Escopo do MVP
- suportar PDF, DOCX, XLSX, XML, HTML, CSV, TXT e OFX
- processar arquivo ou pasta
- gerar artefatos padronizados por arquivo

## Saídas
- metadata.json
- content.json
- index.json
- summary.md
