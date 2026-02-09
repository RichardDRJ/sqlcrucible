"""Tests for automodel stub code generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Mapped

from sqlcrucible.stubs.codegen import (
    build_import_block,
    construct_model_def,
    generate_model_defs_for_entity,
    sa_field_type,
)

from tests.stubs.sample_models import (
    CustomSATypeChild,
    Dog,
    SimpleTrack,
    StubAuthor,
    StubBook,
    _CustomSAModel,
)


def test_sa_field_type_from_annotation():
    sa_type = SimpleTrack.__sqlalchemy_type__
    result = sa_field_type(sa_type, "title")
    assert result == Mapped[str]


def test_sa_field_type_column_property_fallback():
    sa_type = Dog.__sqlalchemy_type__
    result = sa_field_type(sa_type, "name")
    assert result is str


def test_sa_field_type_relationship_property():
    sa_type = StubBook.__sqlalchemy_type__
    result = sa_field_type(sa_type, "author")
    assert result == Mapped[StubAuthor.__sqlalchemy_type__]


def test_sa_field_type_unsupported_raises():
    sa_type = SimpleTrack.__sqlalchemy_type__
    mock_attrs = MagicMock()
    mock_prop = MagicMock(spec=[])
    mock_attrs.get.return_value = mock_prop
    mock_mapper = MagicMock()
    mock_mapper.attrs = mock_attrs

    with (
        patch("sqlcrucible.stubs.codegen.get_annotations", return_value={}),
        patch("sqlcrucible.stubs.codegen.inspect", return_value=mock_mapper),
        pytest.raises(TypeError, match="Could not determine type"),
    ):
        sa_field_type(sa_type, "fake_field")


def test_construct_model_def_has_all_fields():
    sa_type = SimpleTrack.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    for field_name in ("id", "title", "duration_seconds"):
        assert field_name in classdef.class_def


def test_construct_model_def_uses_instrumented_attribute():
    sa_type = SimpleTrack.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    assert "InstrumentedAttribute[" in classdef.class_def


def test_construct_model_def_excludes_self_imports():
    sa_type = SimpleTrack.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    assert sa_type.__module__ not in classdef.imports


def test_build_import_block_excludes_current_module():
    imports = ["foo.bar", "foo.bar.baz", "other.module"]
    result = build_import_block(imports, "foo.bar")
    assert "foo.bar" not in result.split("\n")
    assert "import foo.bar.baz" not in result
    assert "import other.module" in result


def test_build_import_block_deduplicates():
    imports = ["foo.bar", "foo.bar", "baz.qux"]
    result = build_import_block(imports, "unrelated")
    assert result.count("import foo.bar") == 1


def test_build_import_block_sorts():
    imports = ["zebra", "alpha", "middle"]
    result = build_import_block(imports, "unrelated")
    lines = result.strip().split("\n")
    assert lines == ["import alpha", "import middle", "import zebra"]


def test_generate_model_defs_skips_custom_sa_type():
    classdefs = generate_model_defs_for_entity(CustomSATypeChild)
    sources = [cd.source for cd in classdefs]
    assert _CustomSAModel not in sources


def test_generate_model_defs_includes_automodels_around_custom_sa_type():
    classdefs = generate_model_defs_for_entity(CustomSATypeChild)
    sources = [cd.source for cd in classdefs]
    assert CustomSATypeChild.__sqlalchemy_type__ in sources


def test_custom_sa_type_child_automodel_derives_from_custom_sa_type():
    sa_type = CustomSATypeChild.__sqlalchemy_type__
    assert issubclass(sa_type, _CustomSAModel)
