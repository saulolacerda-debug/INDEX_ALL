# MANUTENCAO

Guia curto para manter o `INDEX_ALL` limpo, funcional e pronto para evolucao.

## Objetivo

Manter o repositorio:

- sem dados operacionais ou temporarios versionados
- com ambiente local previsivel
- pronto para novos testes, ajustes e releases

## Regras do dia a dia

- Trabalhe sobre o branch `main`, salvo quando houver uma feature isolada.
- Nao versione arquivos de `data/raw`, `data/processed` ou `data/samples`.
- Preserve apenas os arquivos `.gitkeep` nas pastas de dados.
- Nao suba `.env`, `.venv`, caches, outputs de teste ou artefatos locais.

## Estrutura que deve permanecer

Manter sempre:

- `src/`
- `tests/`
- `scripts/`
- `docs/`
- `data/raw/.gitkeep`
- `data/raw/entrada_atual/.gitkeep`
- `data/processed/.gitkeep`
- `data/samples/.gitkeep`
- `README.md`
- `pyproject.toml`
- `requirements.txt`

## Antes de cada commit

Checklist rapido:

1. Rode `git status`.
2. Confirme que nao existem arquivos de dados ou saidas operacionais prontos para subir.
3. Rode `python -m pytest -q`.
4. Revise o diff com `git diff`.
5. So entao faca o commit.

## Dados e processamento

- Use `data/raw/entrada_atual` apenas como area temporaria de entrada.
- Considere `data/processed` como saida descartavel de execucao.
- Se precisar validar processamento real, prefira usar uma pasta temporaria fora do repositorio.
- Ao terminar testes operacionais, limpe os dados locais novamente.

## Ambiente local

- `.venv` pode ficar localmente para acelerar o trabalho.
- `.env` pode ficar localmente para OCR, Azure e outras configuracoes sensiveis.
- `.vscode` e opcional; mantenha apenas se estiver te ajudando no fluxo.

## Comandos uteis

Executar testes:

```powershell
python -m pytest -q
```

Executar o indexador:

```powershell
python -m index_all.main "caminho\\do\\arquivo-ou-pasta"
```

Instalar em modo editavel:

```powershell
pip install -r requirements.txt
pip install -e .
```

## Limpeza recomendada

Pode remover sem impacto no codigo:

- caches de teste
- `_test_artifacts/`
- `__pycache__/`
- `*.egg-info/`
- arquivos e colecoes gerados dentro de `data/raw` e `data/processed`
- amostras locais usadas apenas para validacao manual

## Fechamento

Se o repositorio estiver com:

- `git status` limpo
- testes passando
- sem dados operacionais locais relevantes

entao ele esta pronto para continuar evoluindo com seguranca.
