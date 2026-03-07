"""Tests for index_all.py"""

import json
import os
import tempfile

import pytest

from index_all import format_table, index_all, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tree(base: str, tree: dict) -> None:
    """Recursively create files described by *tree* under *base*.

    tree format: {name: content_str | nested_dict}
    """
    for name, value in tree.items():
        path = os.path.join(base, name)
        if isinstance(value, dict):
            os.makedirs(path, exist_ok=True)
            _make_tree(path, value)
        else:
            with open(path, "w") as fh:
                fh.write(value)


# ---------------------------------------------------------------------------
# index_all()
# ---------------------------------------------------------------------------


class TestIndexAll:
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = index_all(tmpdir)
        assert result == []

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"hello.txt": "hi"})
            result = index_all(tmpdir)

        assert len(result) == 1
        entry = result[0]
        assert entry["name"] == "hello.txt"
        assert entry["path"] == "hello.txt"
        assert entry["size"] == 2
        assert "modified_at" in entry

    def test_nested_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(
                tmpdir,
                {
                    "a.txt": "aaa",
                    "sub": {
                        "b.py": "import os",
                        "deep": {"c.md": "# hi"},
                    },
                },
            )
            result = index_all(tmpdir)

        paths = {e["path"] for e in result}
        assert "a.txt" in paths
        assert os.path.join("sub", "b.py") in paths
        assert os.path.join("sub", "deep", "c.md") in paths

    def test_extension_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"keep.py": "x", "skip.txt": "y", "also_keep.py": "z"})
            result = index_all(tmpdir, extensions=[".py"])

        names = {e["name"] for e in result}
        assert names == {"keep.py", "also_keep.py"}

    def test_extension_filter_without_dot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"keep.py": "x", "skip.txt": "y"})
            result = index_all(tmpdir, extensions=["py"])

        names = {e["name"] for e in result}
        assert names == {"keep.py"}

    def test_extension_filter_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"file.txt": "x"})
            result = index_all(tmpdir, extensions=[".py"])

        assert result == []

    def test_not_a_directory(self):
        with pytest.raises(NotADirectoryError):
            index_all("/nonexistent/path/that/does/not/exist")

    def test_entry_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"sample.txt": "hello"})
            result = index_all(tmpdir)

        entry = result[0]
        assert set(entry.keys()) == {"path", "name", "size", "modified_at"}
        # modified_at should be an ISO-8601 string ending with +00:00
        assert entry["modified_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# format_table()
# ---------------------------------------------------------------------------


class TestFormatTable:
    def test_empty(self):
        assert format_table([]) == "No files found."

    def test_single_entry(self):
        entries = [{"path": "foo.txt", "name": "foo.txt", "size": 10, "modified_at": "2024-01-01T00:00:00+00:00"}]
        output = format_table(entries)
        assert "foo.txt" in output
        assert "10" in output
        assert "Total: 1 file(s)" in output

    def test_multiple_entries(self):
        entries = [
            {"path": "a.py", "name": "a.py", "size": 5, "modified_at": "2024-01-01T00:00:00+00:00"},
            {"path": "b.py", "name": "b.py", "size": 50, "modified_at": "2024-01-02T00:00:00+00:00"},
        ]
        output = format_table(entries)
        assert "Total: 2 file(s)" in output


# ---------------------------------------------------------------------------
# main() / CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_default_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"cli_test.txt": "data"})
            original_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                rc = main([])
            finally:
                os.chdir(original_dir)
        assert rc == 0

    def test_explicit_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"file.txt": "x"})
            rc = main([tmpdir])
        assert rc == 0

    def test_json_output(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"data.json": "{}"})
            rc = main([tmpdir, "--json"])
            captured = capsys.readouterr()

        assert rc == 0
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "data.json"

    def test_extension_filter_cli(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_tree(tmpdir, {"a.py": "x", "b.txt": "y"})
            rc = main([tmpdir, "-e", ".py", "--json"])
            captured = capsys.readouterr()

        assert rc == 0
        parsed = json.loads(captured.out)
        assert all(e["name"].endswith(".py") for e in parsed)

    def test_invalid_directory(self, capsys):
        rc = main(["/nonexistent/dir"])
        captured = capsys.readouterr()
        assert rc == 1
        assert "Error" in captured.err
