"""Tests for SA type overload stub generation."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from pydantic import Field
from sqlalchemy import MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.annotations import ExcludeSAField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.stubs.codegen import construct_sa_type_stub, specificity_order

_metadata = MetaData()


class _Base(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _metadata}


class _Parent(_Base):
    __sqlalchemy_params__ = {
        "__tablename__": "sa_type_stub_parent",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_identity": "parent"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    kind: Annotated[str, mapped_column(String(50))]


class _Child(_Parent):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "child"}}

    kind: Annotated[str, ExcludeSAField()] = Field(default="child")


class _Alpha(_Base):
    __sqlalchemy_params__ = {"__tablename__": "sa_type_stub_alpha"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)


class _Beta(_Base):
    __sqlalchemy_params__ = {"__tablename__": "sa_type_stub_beta"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)


def test_specificity_order_places_child_before_parent():
    result = specificity_order([_Parent, _Child])
    assert result.index(_Child) < result.index(_Parent)


def test_specificity_order_is_stable_regardless_of_input_order():
    assert specificity_order([_Parent, _Child]) == specificity_order([_Child, _Parent])


def test_specificity_order_includes_ancestors():
    result = specificity_order([_Child])
    assert _Parent in result


def test_specificity_order_includes_disjoint_entities():
    result = specificity_order([_Alpha, _Beta])
    assert _Alpha in result
    assert _Beta in result


def test_specificity_order_returns_empty_for_empty_input():
    assert specificity_order([]) == []


def test_specificity_order_single_entity_appears_first():
    result = specificity_order([_Alpha])
    assert result[0] is _Alpha


def test_specificity_order_contains_no_duplicates():
    result = specificity_order([_Parent, _Child, _Alpha])
    assert len(result) == len(set(result))


def _overload_entity_names(stub: str) -> list[str]:
    """Extract entity type names from overload signatures in order."""
    return re.findall(r"def __getitem__\(cls, item: type\[[\w.]*\.(\w+)\]\)", stub)


def test_sa_type_stub_places_child_overload_before_parent():
    stub = construct_sa_type_stub([_Parent, _Child])
    names = _overload_entity_names(stub)
    assert names.index("_Child") < names.index("_Parent")


def test_sa_type_stub_contains_all_entities():
    entities = [_Alpha, _Parent, _Child]
    stub = construct_sa_type_stub(entities)
    names = _overload_entity_names(stub)
    for entity in entities:
        assert entity.__name__ in names


@pytest.mark.parametrize(
    "entities",
    [
        [_Alpha],
        [_Parent, _Child],
        [_Alpha, _Beta, _Parent],
    ],
    ids=["single", "inheritance", "multiple"],
)
def test_sa_type_stub_has_fallback_overload(entities):
    stub = construct_sa_type_stub(entities)
    assert "def __getitem__(cls, item: type) -> type: ..." in stub


@pytest.mark.parametrize(
    "entities",
    [
        [_Alpha],
        [_Parent, _Child],
        [_Alpha, _Beta, _Parent, _Child],
    ],
    ids=["single", "inheritance", "multiple"],
)
def test_sa_type_stub_imports_all_entity_modules(entities):
    stub = construct_sa_type_stub(entities)
    for entity in entities:
        assert f"import {entity.__module__}" in stub
