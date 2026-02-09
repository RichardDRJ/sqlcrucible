"""Tests for stub file generation and error paths."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlcrucible.stubs import _write_to_stub_file, generate_stubs
from sqlcrucible.stubs.codegen import construct_model_def

from tests.stubs.sample_models import SimpleTrack


@pytest.fixture
def stubs_root(tmp_path: Path) -> Path:
    return tmp_path / "stubs"


def test_write_stub_creates_init_pyi_for_nonexistent_package(stubs_root: Path):
    sa_type = SimpleTrack.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    module_name = classdef.module

    with patch("sqlcrucible.stubs._package_exists_in_source", return_value=False):
        _write_to_stub_file([classdef], stubs_root, module_name)

    parts = module_name.split(".")
    for i in range(1, len(parts)):
        package_dir = stubs_root.joinpath(*parts[:i])
        init_pyi = package_dir / "__init__.pyi"
        assert init_pyi.exists(), f"Expected {init_pyi} to exist for non-source package"


def test_write_stub_skips_init_pyi_for_source_package(stubs_root: Path):
    sa_type = SimpleTrack.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    module_name = classdef.module

    with patch("sqlcrucible.stubs._package_exists_in_source", return_value=True):
        _write_to_stub_file([classdef], stubs_root, module_name)

    parts = module_name.split(".")
    for i in range(1, len(parts)):
        package_dir = stubs_root.joinpath(*parts[:i])
        init_pyi = package_dir / "__init__.pyi"
        assert not init_pyi.exists(), f"Expected {init_pyi} to NOT exist for source package"


def test_generate_stubs_no_entities_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="No SQLCrucibleEntity subclasses found"):
            generate_stubs(["json"], output_dir=tmpdir)
