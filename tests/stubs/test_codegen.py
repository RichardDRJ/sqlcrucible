"""Tests for SA type overload stub generation."""

from __future__ import annotations

import re

import pytest

from sqlcrucible.entity.core import SQLCrucibleEntity
from sqlcrucible.stubs.codegen import subclass_first, construct_sa_type_stub

from tests.stubs.sample_models import (
    Animal,
    Dog,
    EntityWithExcludedField,
    SimpleTrack,
    StubAuthor,
    StubBook,
)


def _entity_order(result: list[type[SQLCrucibleEntity]], entities: list[type]) -> list[type]:
    """Filter result to only the given entity types, preserving order."""
    entity_set = set(entities)
    return [it for it in result if it in entity_set]


def test_subclass_first_child_before_parent():
    result = subclass_first([Animal, Dog])
    order = _entity_order(result, [Animal, Dog])
    assert order == [Dog, Animal]


def test_subclass_first_child_before_parent_regardless_of_input_order():
    result_parent_first = subclass_first([Animal, Dog])
    result_child_first = subclass_first([Dog, Animal])
    order_a = _entity_order(result_parent_first, [Animal, Dog])
    order_b = _entity_order(result_child_first, [Animal, Dog])
    assert order_a == order_b == [Dog, Animal]


def test_subclass_first_includes_ancestors():
    result = subclass_first([Dog])
    assert Animal in result


def test_subclass_first_disjoint_entities():
    result = subclass_first([SimpleTrack, StubAuthor])
    assert SimpleTrack in result
    assert StubAuthor in result


def test_subclass_first_empty():
    assert subclass_first([]) == []


def test_subclass_first_single_entity():
    result = subclass_first([SimpleTrack])
    assert result[0] is SimpleTrack


def test_subclass_first_no_duplicates():
    result = subclass_first([Animal, Dog, SimpleTrack])
    assert len(result) == len(set(result))


def _overload_entity_names(stub: str) -> list[str]:
    """Extract entity type names from overload signatures in order."""
    return re.findall(r"def __getitem__\(cls, item: type\[[\w.]*\.(\w+)\]\)", stub)


def test_sa_type_stub_subclass_overload_before_parent():
    stub = construct_sa_type_stub([Animal, Dog])
    names = _overload_entity_names(stub)
    assert names.index("Dog") < names.index("Animal")


def test_sa_type_stub_contains_all_entities():
    entities = [SimpleTrack, Animal, Dog]
    stub = construct_sa_type_stub(entities)
    names = _overload_entity_names(stub)
    for entity in entities:
        assert entity.__name__ in names


@pytest.mark.parametrize(
    "entities",
    [
        [SimpleTrack],
        [Animal, Dog],
        [SimpleTrack, StubAuthor, StubBook],
    ],
    ids=["single", "inheritance", "multiple-disjoint"],
)
def test_sa_type_stub_has_fallback_overload(entities):
    stub = construct_sa_type_stub(entities)
    assert "def __getitem__(cls, item: type) -> type: ..." in stub


@pytest.mark.parametrize(
    "entities",
    [
        [SimpleTrack],
        [Animal, Dog],
        [SimpleTrack, EntityWithExcludedField, StubAuthor, StubBook],
    ],
    ids=["single", "inheritance", "multi-module"],
)
def test_sa_type_stub_imports_all_entity_modules(entities):
    stub = construct_sa_type_stub(entities)
    for entity in entities:
        assert f"import {entity.__module__}" in stub
