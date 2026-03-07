# INDEX_ALL

A simple Python CLI utility that **recursively indexes all files** in a directory and reports their path, size, and last-modified timestamp.

## Usage

```
python index_all.py [directory] [options]
```

| Argument / Option | Description |
|---|---|
| `directory` | Root directory to index (defaults to `.`) |
| `-e EXT [EXT …]` | Filter by file extension(s), e.g. `-e .py .txt` |
| `--json` | Output as JSON instead of a table |

### Examples

Index the current directory:
```bash
python index_all.py
```

Index a specific directory, filtered to Python files only:
```bash
python index_all.py /path/to/project -e .py
```

Output as JSON:
```bash
python index_all.py /path/to/project --json
```

## Running tests

```bash
python -m pytest test_index_all.py -v
```

