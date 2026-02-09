"""Tests for stub file generation and error paths."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sqlcrucible.stubs import _write_to_stub_file, generate_stubs
from sqlcrucible.stubs.codegen import ClassDef


def _stub_classdef(module: str) -> ClassDef:
    return ClassDef(source=object, module=module, imports=[], class_def="class Fake: pass")


@pytest.fixture
def stubs_root(tmp_path: Path) -> Path:
    return tmp_path / "stubs"


def test_write_stub_creates_init_pyi_for_nonexistent_package(stubs_root: Path):
    module_name = "nonexistent.fake.module"
    _write_to_stub_file([_stub_classdef(module_name)], stubs_root, module_name)

    for package in ("nonexistent", "nonexistent/fake"):
        init_pyi = stubs_root / package / "__init__.pyi"
        assert init_pyi.exists(), f"Expected {init_pyi} to exist for non-source package"


def test_write_stub_skips_init_pyi_for_source_package(stubs_root: Path):
    module_name = "sqlcrucible.stubs.fakefile"
    _write_to_stub_file([_stub_classdef(module_name)], stubs_root, module_name)

    for package in ("sqlcrucible", "sqlcrucible/stubs"):
        init_pyi = stubs_root / package / "__init__.pyi"
        assert not init_pyi.exists(), f"Expected {init_pyi} to NOT exist for source package"


def test_generate_stubs_no_entities_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="No SQLCrucibleEntity subclasses found"):
            generate_stubs(["json"], output_dir=tmpdir)
