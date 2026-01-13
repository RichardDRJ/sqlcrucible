from tests.conversion.conftest import SourceItem, TargetItem
from typing import Any

import pytest

from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.mappings import MappingConverterFactory


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (dict, dict),
        (dict[str, int], dict[str, int]),
        (dict[int, str], dict[int, str]),
    ],
)
def test_mapping_factory_matches_dict_types(source_tp, target_tp):
    mapping_factory = MappingConverterFactory()
    assert mapping_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (list, dict),
        (dict, list),
        (set, dict),
    ],
)
def test_mapping_factory_does_not_match_non_dicts(source_tp, target_tp):
    mapping_factory = MappingConverterFactory()
    assert not mapping_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp", "input_value", "expected_output"),
    [
        (dict[str, int], dict[str, int], {"a": 1, "b": 2}, {"a": 1, "b": 2}),
        (dict, dict, {"a": 1, "b": 2}, {"a": 1, "b": 2}),
        (
            dict[str, Any],
            dict[str, Any],
            {"a": None, "b": SourceItem(1)},
            {"a": None, "b": SourceItem(1)},
        ),
        (
            dict[str, SourceItem],
            dict[str, TargetItem],
            {"item": SourceItem(1)},
            {"item": TargetItem(2)},
        ),
        (
            dict,
            dict,
            {},
            {},
        ),
    ],
)
def test_dict_to_dict_maps_correctly(
    registry: ConverterRegistry,
    source_tp,
    target_tp,
    input_value,
    expected_output,
) -> None:
    conv = registry.resolve(source_tp, target_tp)
    assert conv is not None
    actual_output = conv.convert(input_value)
    assert actual_output == expected_output
