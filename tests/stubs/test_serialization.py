"""Tests for type annotation serialization."""

from __future__ import annotations

from typing import Annotated, Union
from uuid import UUID

from sqlalchemy.orm import Mapped

from sqlcrucible.stubs.serialization import TypeDef, fqn, to_typedef


def test_to_typedef_builtin_type():
    result = to_typedef(int)
    assert result == TypeDef(imports=[], type_def="int")


def test_to_typedef_non_builtin_type():
    result = to_typedef(UUID)
    assert result == TypeDef(imports=["uuid"], type_def="uuid.UUID")


def test_to_typedef_string_annotation():
    result = to_typedef("MyForwardRef")
    assert result == TypeDef(imports=[], type_def='"MyForwardRef"')


def test_to_typedef_none():
    result = to_typedef(None)
    assert result == TypeDef(imports=[], type_def="None")


def test_to_typedef_none_type():
    result = to_typedef(type(None))
    assert result == TypeDef(imports=[], type_def="None")


def test_to_typedef_annotated_unwraps():
    result = to_typedef(Annotated[str, "some metadata"])
    assert result == TypeDef(imports=[], type_def="str")


def test_to_typedef_mapped_unwraps():
    result = to_typedef(Mapped[int])
    assert result == TypeDef(imports=[], type_def="int")


def test_to_typedef_mapped_no_args():
    result = to_typedef(Mapped)
    assert result == TypeDef(imports=["sqlalchemy.orm.base"], type_def="sqlalchemy.orm.base.Mapped")


def test_to_typedef_union():
    result = to_typedef(Union[str, None])
    assert result.type_def == "typing.Union[str, None]"
    assert "typing" in result.imports


def test_to_typedef_generic():
    result = to_typedef(list[str])
    assert result == TypeDef(imports=[], type_def="list[str]")


def test_to_typedef_non_type_non_generic():
    result = to_typedef(42)
    assert result == TypeDef(imports=["typing"], type_def="typing.Any")


def test_fqn_builtin():
    assert fqn(int) == "int"


def test_fqn_non_builtin():
    assert fqn(UUID) == "uuid.UUID"
