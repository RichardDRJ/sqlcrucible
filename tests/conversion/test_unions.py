from tests.conversion.conftest import SourceItem, TargetItem

from typing import Any, cast

from sqlcrucible.conversion.caching import CachingConverter
from sqlcrucible.conversion.noop import NoOpConverter

import pytest

from sqlcrucible.conversion.registry import Converter, ConverterRegistry
from sqlcrucible.conversion.unions import UnionConverterFactory


def _unwrap(converter: Converter[Any, Any]) -> Converter[Any, Any]:
    """Unwrap a CachingConverter to get the inner converter."""
    if isinstance(converter, CachingConverter):
        return cast(Converter[Any, Any], converter._inner)
    return converter


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int | str, str),  # union source
        (int, int | str),  # union target
        (int | str, str | float),  # both unions
        (list | set, set),  # sequence union
    ],
)
def test_union_factory_matches_union_types(
    source_tp,
    target_tp,
):
    union_factory = UnionConverterFactory()
    assert union_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int, str),
        (list, set),
        (dict, list),
    ],
)
def test_union_factory_does_not_match_non_unions(
    source_tp,
    target_tp,
):
    union_factory = UnionConverterFactory()
    assert not union_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (str | int, str | int),
        (int | str, str | int),
        (int, str | int),
        (str, str | int),
        (list, list | set),
        (set | list, list | set),
    ],
)
def test_source_subset_of_target_union_uses_noop(
    registry: ConverterRegistry,
    source_tp,
    target_tp,
):
    conv = registry.resolve(source_tp, target_tp)
    assert conv is not None
    assert isinstance(_unwrap(conv), NoOpConverter)


@pytest.mark.parametrize(
    ("source_tp", "target_tp", "input_value", "expected_output"),
    [
        (list[str], set[str] | list[int], ["abcd", "efgh"], {"abcd", "efgh"}),
        (list[str], set[int] | list[str], ["abcd", "efgh"], ["abcd", "efgh"]),
        # `list[SourceItem]` cannot be converted to `list[int]` so should be converted to `list[TargetItem]`
        (
            list[SourceItem],
            list[int] | list[TargetItem],
            [SourceItem(1), SourceItem(2)],
            [TargetItem(2), TargetItem(4)],
        ),
        # `list[SourceItem]` cannot be converted to `list[int]` but can be converted to `set[SourceItem]` and
        # `list[TargetItem]` so should be converted to the first convertible type.
        (
            list[SourceItem],
            list[int] | set[SourceItem] | list[TargetItem],
            [SourceItem(1), SourceItem(2)],
            {SourceItem(1), SourceItem(2)},
        ),
        # `list[SourceItem | None]` cannot be converted to `list[int]` or `set[SourceItem]` so should be
        # converted to `list[TargetItem | None]`
        (
            list[SourceItem | None],
            list[int] | set[SourceItem] | list[TargetItem | None],
            [None, SourceItem(1)],
            [None, TargetItem(2)],
        ),
    ],
)
def test_nested_conversion_applied_in_union(
    registry: ConverterRegistry, source_tp, target_tp, input_value, expected_output
):
    conv = registry.resolve(source_tp, target_tp)
    assert conv is not None
    actual_output = conv.convert(input_value)
    assert actual_output == expected_output


def test_no_converter_returned_if_not_all_input_types_can_be_handled(registry: ConverterRegistry):
    assert registry.resolve(int | None, int) is None
