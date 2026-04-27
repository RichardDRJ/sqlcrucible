"""Tests for AnnotatedUnwrappingFactory."""

from typing import Annotated, Any

import pytest
from sqlalchemy.orm import Mapped

from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.unwrap import AnnotatedUnwrappingFactory
from tests.conversion.conftest import SourceItem, TargetItem


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (Annotated[int, "meta"], str),
        (int, Annotated[str, "meta"]),
        (Annotated[int, "meta"], Annotated[str, "other"]),
        (Mapped[int], str),
        (int, Mapped[str]),
    ],
    ids=[
        "annotated_source",
        "annotated_target",
        "both_annotated",
        "mapped_source",
        "mapped_target",
    ],
)
def test_matches_when_either_side_is_wrapped(source_tp: Any, target_tp: Any):
    factory = AnnotatedUnwrappingFactory()
    assert factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int, str),
        (list[int], set[str]),
    ],
    ids=["plain_types", "generic_types"],
)
def test_does_not_match_unwrapped_types(source_tp: Any, target_tp: Any):
    factory = AnnotatedUnwrappingFactory()
    assert not factory.matches(source_tp, target_tp)


def test_delegates_to_registry_with_unwrapped_types(registry: ConverterRegistry):
    factory = AnnotatedUnwrappingFactory()
    converter = factory.converter(
        Annotated[SourceItem, "some_marker"],
        TargetItem,
        registry,
    )
    assert converter is not None
    result = converter.convert(SourceItem(1))
    assert result == TargetItem(2)


def test_registry_resolves_annotated_source_via_unwrapping(registry: ConverterRegistry):
    unwrapping_registry = ConverterRegistry(AnnotatedUnwrappingFactory(), *registry)
    conv = unwrapping_registry.resolve(Annotated[SourceItem, "marker"], TargetItem)
    assert conv is not None
    assert conv.convert(SourceItem(3)) == TargetItem(6)


def test_registry_resolves_annotated_list_via_unwrapping(registry: ConverterRegistry):
    unwrapping_registry = ConverterRegistry(AnnotatedUnwrappingFactory(), *registry)
    conv = unwrapping_registry.resolve(
        Annotated[list[SourceItem], "marker"],
        list[TargetItem],
    )
    assert conv is not None
    assert conv.convert([SourceItem(1), SourceItem(2)]) == [TargetItem(2), TargetItem(4)]


def test_registry_resolves_mapped_source_via_unwrapping(registry: ConverterRegistry):
    unwrapping_registry = ConverterRegistry(AnnotatedUnwrappingFactory(), *registry)
    conv = unwrapping_registry.resolve(Mapped[SourceItem], TargetItem)
    assert conv is not None
    assert conv.convert(SourceItem(5)) == TargetItem(10)
