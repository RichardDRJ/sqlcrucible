"""Tests for build_import_block."""

from __future__ import annotations

from sqlcrucible.stubs.codegen import build_import_block


def test_excludes_current_module():
    imports = ["foo.bar", "foo.bar.baz", "other.module"]
    result = build_import_block(imports, "foo.bar")
    assert "foo.bar" not in result.split("\n")
    assert "import foo.bar.baz" not in result
    assert "import other.module" in result


def test_deduplicates_repeated_imports():
    imports = ["foo.bar", "foo.bar", "baz.qux"]
    result = build_import_block(imports, "unrelated")
    assert result.count("import foo.bar") == 1


def test_sorts_imports_alphabetically():
    imports = ["zebra", "alpha", "middle"]
    result = build_import_block(imports, "unrelated")
    lines = result.strip().split("\n")
    assert lines == ["import alpha", "import middle", "import zebra"]
