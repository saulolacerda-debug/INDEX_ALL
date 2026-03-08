# PROMPTS.md

## 1. Implementação de módulo

Leia `AI_CONTEXT.md` e `ARCHITECTURE.md`.
Implemente o arquivo solicitado em Python, de forma funcional, limpa e modular.
Respeite a separação entre ingestão, parsing, indexação e saída.
Entregue código completo, não pseudocódigo.

## 2. Implementação de parser

Leia `AI_CONTEXT.md` e `ARCHITECTURE.md`.
Implemente o parser `{NOME_DO_PARSER}`.
O parser deve:
- receber um caminho de arquivo
- extrair conteúdo relevante
- devolver blocos padronizados
- preencher `parser_metadata`
- falhar de modo controlado quando necessário

## 3. Refatoração segura

Leia `AI_CONTEXT.md`, `ARCHITECTURE.md` e o arquivo alvo.
Refatore preservando comportamento e melhorando clareza, organização e robustez.
Evite quebrar a interface pública existente.

## 4. Criação de testes

Leia `AI_CONTEXT.md`, `ARCHITECTURE.md` e o módulo alvo.
Crie testes objetivos e executáveis com `pytest`.
Cubra caso feliz, caso vazio e falha controlada.

## 5. Evolução do roadmap

Leia `ROADMAP.md`.
Proponha o próximo passo de implementação com base no estágio atual do repositório.
Explique dependências, impacto e prioridade técnica.

## 6. Implementação temática futura

Leia `AI_CONTEXT.md` e `ARCHITECTURE.md`.
Proponha uma extensão temática sobre o núcleo do INDEX_ALL sem contaminar o core.
Use abordagem por pack ou plugin.
