"""Tests for CachingConverter identity-map integration.

Verifies that CachingConverter returns cached results when the same source
object (by id) appears across different conversion paths — direct entity
conversion, as an element inside a sequence, and as a value inside a dict.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from sqlcrucible.conversion import default_registry
from sqlcrucible.conversion.caching import CachingConverter, _identity_map
from sqlcrucible.conversion.dicts import DictConverter, DictInfo
from sqlcrucible.conversion.registry import Converter
from sqlcrucible.conversion.sequences import SequenceConverter


@dataclass
class Source:
    value: int


@dataclass
class Target:
    value: int


class DoublingConverter(Converter[Source, Target]):
    """Test converter that tracks how many times convert() is called."""

    def __init__(self) -> None:
        self.call_count = 0

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return True

    def convert(self, source: Source) -> Target:
        self.call_count += 1
        return Target(value=source.value * 2)

    def safe_convert(self, source: Source) -> Target:
        self.call_count += 1
        return Target(value=source.value * 2)


def test_cache_hit_returns_cached_result() -> None:
    """When a source's id is in the identity map, the cached result is returned."""
    inner = DoublingConverter()
    converter = CachingConverter(inner)
    source = Source(1)
    cached = Target(99)

    with _identity_map() as identity_map:
        identity_map[id(source)] = cached
        result = converter.convert(source)

    assert result is cached
    assert inner.call_count == 0


def test_cache_miss_delegates_to_inner() -> None:
    """When a source's id is not in the identity map, the inner converter is called."""
    inner = DoublingConverter()
    converter = CachingConverter(inner)
    source = Source(5)

    with _identity_map():
        result = converter.convert(source)

    assert result == Target(10)
    assert inner.call_count == 1


def test_no_identity_map_delegates_to_inner() -> None:
    """When called outside an _identity_map context, the inner converter is called directly."""
    inner = DoublingConverter()
    converter = CachingConverter(inner)

    result = converter.convert(Source(3))

    assert result == Target(6)
    assert inner.call_count == 1


def test_safe_convert_uses_cache() -> None:
    """safe_convert also checks the identity map before delegating."""
    inner = DoublingConverter()
    converter = CachingConverter(inner)
    source = Source(1)
    cached = Target(99)

    with _identity_map() as identity_map:
        identity_map[id(source)] = cached
        result = converter.safe_convert(source)

    assert result is cached
    assert inner.call_count == 0


def test_cache_hit_inside_sequence() -> None:
    """Elements inside a SequenceConverter use the identity map for cache hits."""
    inner = DoublingConverter()
    cached_source = Source(1)
    uncached_source = Source(2)
    cached_target = Target(99)

    seq = SequenceConverter(list, CachingConverter(inner))

    with _identity_map() as identity_map:
        identity_map[id(cached_source)] = cached_target
        result = seq.convert([cached_source, uncached_source])

    assert result[0] is cached_target
    assert result[1] == Target(4)
    assert inner.call_count == 1


def test_cache_hit_inside_dict() -> None:
    """Values inside a DictConverter use the identity map for cache hits."""
    inner = DoublingConverter()
    cached_source = Source(1)
    uncached_source = Source(2)
    cached_target = Target(99)

    target_info = DictInfo.create(dict[str, Target])
    dict_conv = DictConverter(
        target_info,
        field_converters={},
        extra_converter=CachingConverter(inner),
    )

    with _identity_map() as identity_map:
        identity_map[id(cached_source)] = cached_target
        result = dict_conv.convert({"a": cached_source, "b": uncached_source})

    assert result["a"] is cached_target
    assert result["b"] == Target(4)
    assert inner.call_count == 1


def test_shared_source_across_entity_and_sequence() -> None:
    """The same source object returns the same cached result whether accessed
    directly or as an element of a sequence."""
    inner = DoublingConverter()
    shared = Source(1)
    other = Source(2)
    cached_shared = Target(99)

    caching = CachingConverter(inner)
    seq = SequenceConverter(list, caching)

    with _identity_map() as identity_map:
        identity_map[id(shared)] = cached_shared
        direct = caching.convert(shared)
        from_list = seq.convert([shared, other])

    assert direct is cached_shared
    assert from_list[0] is cached_shared
    assert direct is from_list[0]
    assert inner.call_count == 1


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int, int),
        (list[int], list[int]),
        (dict[str, int], dict[str, int]),
        (int | str, int | str),
    ],
    ids=["noop", "sequence", "dict", "union"],
)
def test_default_registry_resolves_caching_converters(
    source_tp: Any,
    target_tp: Any,
) -> None:
    """Converters resolved from default_registry are wrapped with CachingConverter."""
    converter = default_registry.resolve(source_tp, target_tp)
    assert isinstance(converter, CachingConverter)


def test_default_registry_sequence_converter_caches_by_identity() -> None:
    """A list converted twice through default_registry returns the same object."""
    converter = default_registry.resolve(list[int], list[int])
    assert converter is not None

    source = [1, 2, 3]

    with _identity_map():
        first = converter.convert(source)
        second = converter.convert(source)

    assert first is second


def test_default_registry_dict_converter_caches_by_identity() -> None:
    """A dict converted twice through default_registry returns the same object."""
    converter = default_registry.resolve(dict[str, int], dict[str, int])
    assert converter is not None

    source = {"a": 1, "b": 2}

    with _identity_map():
        first = converter.convert(source)
        second = converter.convert(source)

    assert first is second
