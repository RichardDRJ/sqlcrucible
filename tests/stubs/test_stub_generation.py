"""Tests for stub file generation and error paths."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sqlcrucible.stubs import _finalize_stub_package, _stub_path, generate_stubs


@pytest.fixture
def stubs_root(tmp_path: Path) -> Path:
    return tmp_path / "stubs"


@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        ("sqlcrucible.entity.sa_type", "sqlcrucible-stubs/entity/sa_type.pyi"),
        ("sqlcrucible.generated.myapp.models", "sqlcrucible-stubs/generated/myapp/models.pyi"),
    ],
)
def test_stub_path_targets_stubs_package(stubs_root: Path, module_name: str, expected: str):
    assert _stub_path(stubs_root, module_name) == stubs_root / expected


def test_finalize_flags_package_partial_and_marks_stub_only_dirs(stubs_root: Path):
    generated = stubs_root / "sqlcrucible-stubs" / "generated"
    generated.mkdir(parents=True)
    (generated / "models.pyi").write_text("class Fake: ...")

    _finalize_stub_package(stubs_root)

    assert (stubs_root / "sqlcrucible-stubs" / "py.typed").read_text() == "partial\n"
    assert (generated / "__init__.pyi").read_text() == ""


def test_finalize_mirrors_real_package_init_to_avoid_shadowing(stubs_root: Path):
    (stubs_root / "sqlcrucible-stubs").mkdir(parents=True)

    _finalize_stub_package(stubs_root)

    init_pyi = (stubs_root / "sqlcrucible-stubs" / "__init__.pyi").read_text()
    assert "SAType" in init_pyi


def test_generate_stubs_no_entities_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="No SQLCrucibleEntity subclasses found"):
            generate_stubs(["json"], output_dir=tmpdir)
