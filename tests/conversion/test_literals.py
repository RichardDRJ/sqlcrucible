from typing import Literal

import pytest

from sqlcrucible.conversion.exceptions import TypeMismatchError
from sqlcrucible.conversion.literals import LiteralConverter, LiteralConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (Literal["a"], Literal["a"]),
        (Literal["a"], Literal["a", "b"]),
        (Literal["a", "b"], Literal["a", "b"]),
        (Literal["a", "b"], Literal["a", "b", "c"]),
        (Literal[1], Literal[1, 2]),
        (Literal[1, 2], Literal[1, 2]),
        (Literal[True], Literal[True, False]),
    ],
)
def test_literal_converter_factory_matches_when_source_is_subset(source_tp, target_tp):
    factory = LiteralConverterFactory()
    assert factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (Literal["a", "b"], Literal["a"]),
        (Literal["a", "c"], Literal["a", "b"]),
        (Literal[1, 2, 3], Literal[1, 2]),
        (Literal["x"], Literal["a", "b"]),
    ],
)
def test_literal_converter_factory_does_not_match_when_source_not_subset(source_tp, target_tp):
    factory = LiteralConverterFactory()
    assert not factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (str, Literal["a"]),
        (Literal["a"], str),
        (int, Literal[1, 2]),
        (Literal[1], int),
        (str, str),
    ],
)
def test_literal_converter_factory_does_not_match_non_literal_types(source_tp, target_tp):
    factory = LiteralConverterFactory()
    assert not factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("value", "target_tp"),
    [
        ("a", Literal["a"]),
        ("a", Literal["a", "b"]),
        ("b", Literal["a", "b"]),
        (1, Literal[1, 2, 3]),
        (2, Literal[1, 2, 3]),
        (3, Literal[1, 2, 3]),
        (True, Literal[True, False]),
        (False, Literal[True, False]),
    ],
)
def test_literal_converter_returns_value_when_valid(value, target_tp):
    converter = LiteralConverter(target_tp)
    assert converter.convert(value) is value


@pytest.mark.parametrize(
    ("value", "target_tp"),
    [
        ("b", Literal["a"]),
        ("c", Literal["a", "b"]),
        (3, Literal[1, 2]),
        ("1", Literal[1]),
        (True, Literal["true"]),
    ],
)
def test_literal_converter_raises_error_when_value_not_in_literal(value, target_tp):
    converter = LiteralConverter(target_tp)
    with pytest.raises(TypeMismatchError) as exc_info:
        converter.convert(value)
    assert exc_info.value.source is value
    assert exc_info.value.target_type is target_tp


def test_literal_converter_error_message_contains_allowed_values():
    converter = LiteralConverter(Literal["a", "b", "c"])
    with pytest.raises(TypeMismatchError) as exc_info:
        converter.convert("x")
    assert "x" in str(exc_info.value)
    assert "'a'" in str(exc_info.value)
    assert "'b'" in str(exc_info.value)
    assert "'c'" in str(exc_info.value)


def test_literal_converter_via_registry(registry: ConverterRegistry):
    source_tp = Literal["a"]
    target_tp = Literal["a", "b"]
    converter = registry.resolve(source_tp, target_tp)
    assert converter is not None
    assert converter.convert("a") == "a"


def test_literal_converter_via_registry_returns_none_when_not_subset(registry: ConverterRegistry):
    source_tp = Literal["a", "c"]
    target_tp = Literal["a", "b"]
    converter = registry.resolve(source_tp, target_tp)
    assert converter is None
