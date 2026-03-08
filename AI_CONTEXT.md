# AI_CONTEXT.md

## Nome do projeto

INDEX_ALL

## Propósito

Construir um app Python local, orientado a arquivos, capaz de ingerir, normalizar, indexar e
sumarizar documentos e datasets heterogêneos do dia a dia.

O projeto deve servir como núcleo base para usos futuros em:

- reforma tributária do consumo
- legislação fiscal
- processos judiciais
- documentos societários
- relatórios contábeis
- XML de documentos fiscais
- arquivos financeiros, inclusive OFX

## Filosofia de construção

O núcleo do sistema deve ser genérico. Ele não deve nascer preso a um domínio temático.
A especialização virá depois, por módulos.

Estratégia correta:

- `index_all` = core universal
- `tax_pack` = inteligência tributária
- `judicial_pack` = inteligência processual
- `accounting_pack` = inteligência contábil
- `corporate_pack` = inteligência societária

## Resultado esperado do core

Para qualquer arquivo suportado, o sistema deve produzir uma representação comum, com:

- metadados
- blocos de conteúdo
- índice navegável
- resumo executivo
- saídas serializadas em JSON e Markdown

## Restrições do MVP

No MVP, priorizar:

- funcionamento local
- robustez da extração
- estruturação mínima consistente
- saída padronizada

No MVP, não priorizar:

- OCR avançado
- UI complexa
- permissões multiusuário
- dashboards sofisticados
- workflows empresariais extensos

## Estilo de código esperado

- Python 3.12+
- código limpo, modular e tipado quando razoável
- funções curtas
- nomes descritivos
- baixo acoplamento
- tratamento honesto de erro
- logs simples e úteis
- parsers independentes por formato
- pipeline explícito e legível

## Regras para futuras implementações com IA

Ao implementar ou refatorar arquivos deste projeto, a IA deve:

1. ler `AI_CONTEXT.md` e `ARCHITECTURE.md` antes de propor mudanças;
2. preservar a separação entre ingestão, parsing, indexação e saída;
3. evitar acoplamento do core com lógica tributária ou judicial;
4. preferir expansão por módulos;
5. manter compatibilidade com o schema universal de saída;
6. entregar código funcional, não apenas pseudocódigo.

## Convenções operacionais

- arquivos de entrada em `data/raw` ou `data/samples`
- artefatos gerados em `data/processed`
- documentação viva na raiz e em `docs`
- código-fonte em `src/index_all`
- testes em `tests`

## Objetivo arquitetural de longo prazo

Transformar o INDEX_ALL em infraestrutura base para motores especialistas, inclusive um futuro
motor tributário capaz de operar sobre legislação, regras, cruzamentos e obrigações acessórias.
