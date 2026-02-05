from typing import Any

from typing_extensions import TypedDict

import pytest

from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.dicts import DictConverterFactory, DictInfo
from tests.conversion.conftest import SourceItem, TargetItem


class PersonDict(TypedDict):
    name: str
    age: int


class PartialDict(TypedDict, total=False):
    name: str
    age: int


class NestedDict(TypedDict):
    person: PersonDict
    active: bool


class OpenTypedDict(TypedDict, closed=False):
    name: str
    age: int


class ClosedTypedDict(TypedDict, closed=True):
    name: str
    age: int


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (dict, PersonDict),
        (dict[str, str], PersonDict),
        (dict[str, int], PersonDict),
        (dict, PartialDict),
        (dict, NestedDict),
        (PersonDict, dict),
        (PersonDict, PersonDict),
        (PersonDict, PartialDict),
        (dict, dict),
        (dict[str, int], dict[str, int]),
        (dict[str, int], dict[str, str]),
    ],
)
def test_factory_matches_dict_like_types(source_tp, target_tp):
    factory = DictConverterFactory()
    assert factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (str, PersonDict),
        (list, PersonDict),
        (list[int], dict[str, int]),
        (dict, list),
        (set, dict),
    ],
)
def test_factory_does_not_match_non_dict_types(source_tp, target_tp):
    factory = DictConverterFactory()
    assert not factory.matches(source_tp, target_tp)


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
        (dict, dict, {}, {}),
    ],
)
def test_dict_to_dict_converts_correctly(
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


def test_dict_to_dict_creates_new_reference(registry: ConverterRegistry) -> None:
    """Converting dict to same type creates a new dict (defensive copy)."""
    conv = registry.resolve(dict[str, int], dict[str, int])
    assert conv is not None
    original = {"a": 1, "b": 2}
    result = conv.convert(original)
    assert result == original
    assert result is not original


def test_unparameterized_dict_to_typeddict_returns_none(registry: ConverterRegistry):
    # dict has value type Any, and Any -> str/int cannot be proven valid
    converter = registry.resolve(dict, PersonDict)
    assert converter is None


def test_any_value_dict_to_typeddict_returns_none(registry: ConverterRegistry):
    # dict[str, Any] -> TypedDict[str, int] cannot be proven valid
    # because Any -> int is not provably valid
    converter = registry.resolve(dict[str, Any], PersonDict)
    assert converter is None


def test_unparameterized_dict_to_nested_typeddict_returns_none(
    registry: ConverterRegistry,
):
    # dict has value type Any, and Any -> TypedDict has no converter
    converter = registry.resolve(dict, NestedDict)
    assert converter is None


def test_typeddict_to_plain_dict(registry: ConverterRegistry):
    converter = registry.resolve(PersonDict, dict)
    assert converter is not None
    result = converter.convert({"name": "Alice", "age": 30})
    assert result == {"name": "Alice", "age": 30}


def test_typeddict_to_parameterized_dict(registry: ConverterRegistry):
    converter = registry.resolve(PersonDict, dict[str, Any])
    assert converter is not None
    result = converter.convert({"name": "Alice", "age": 30})
    assert result == {"name": "Alice", "age": 30}


def test_typeddict_to_dict_creates_new_reference(registry: ConverterRegistry):
    """Converting TypedDict to dict creates a new dict."""
    converter = registry.resolve(PersonDict, dict)
    assert converter is not None
    original: PersonDict = {"name": "Alice", "age": 30}
    result = converter.convert(original)
    assert result == original
    assert result is not original


def test_typeddict_to_same_typeddict_creates_copy(registry: ConverterRegistry):
    converter = registry.resolve(PersonDict, PersonDict)
    assert converter is not None
    original: PersonDict = {"name": "Alice", "age": 30}
    result = converter.convert(original)
    assert result == original
    assert result is not original


def test_typeddict_to_compatible_typeddict(registry: ConverterRegistry):
    converter = registry.resolve(PersonDict, PartialDict)
    assert converter is not None
    result = converter.convert({"name": "Alice", "age": 30})
    assert result == {"name": "Alice", "age": 30}


def test_partial_typeddict_to_total_missing_required(registry: ConverterRegistry):
    converter = registry.resolve(PartialDict, PersonDict)
    assert converter is not None
    with pytest.raises(TypeError) as exc_info:
        converter.convert({"name": "Alice"})
    assert "age" in str(exc_info.value)


def test_partial_typeddict_to_total_with_all_fields(registry: ConverterRegistry):
    converter = registry.resolve(PartialDict, PersonDict)
    assert converter is not None
    result = converter.convert({"name": "Alice", "age": 30})
    assert result == {"name": "Alice", "age": 30}


def test_incompatible_key_types_returns_none(registry: ConverterRegistry):
    # dict[int, str] -> dict[str, str] should fail because int != str for keys
    converter = registry.resolve(dict[int, str], dict[str, str])
    assert converter is None


def test_any_key_to_str_key_returns_none(registry: ConverterRegistry):
    # dict (Any keys) -> dict[str, int] should fail because Any -> str is not provable
    converter = registry.resolve(dict, dict[str, int])
    assert converter is None


def test_dictinfo_typeddict_has_str_key_type():
    info = DictInfo.create(PersonDict)
    assert info.key_type is str


def test_dictinfo_parameterized_dict_extracts_key_type():
    info = DictInfo.create(dict[int, str])
    assert info.key_type is int


def test_dictinfo_unparameterized_dict_has_any_key_type():
    info = DictInfo.create(dict)
    assert info.key_type is Any


def test_dictinfo_closed_typeddict_has_no_extra_items():
    info = DictInfo.create(ClosedTypedDict)
    assert info.extra_items is None


def test_dictinfo_open_typeddict_has_extra_items():
    info = DictInfo.create(OpenTypedDict)
    assert info.extra_items is not None
    assert info.extra_items.tp is Any
