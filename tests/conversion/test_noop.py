import pytest

from sqlcrucible.conversion.exceptions import TypeMismatchError
from sqlcrucible.conversion.noop import NoOpConverter, NoOpConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int, int),
        (str, str),
        (float, float),
        (bool, bool),
        (type(None), type(None)),
    ],
)
def test_noop_converter_factory_matches_identical_types(source_tp, target_tp):
    factory = NoOpConverterFactory()
    assert factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (int, str),
        (str, int),
        (list, set),
        (list[int], list[int]),
        (list[int], list[str]),
    ],
)
def test_noop_converter_does_not_match_different_or_generic_types(source_tp, target_tp):
    factory = NoOpConverterFactory()
    assert not factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("tp", "value"),
    [
        (int, 42),
        (str, "hello"),
        (float, 3.14),
        (bool, True),
        (type(None), None),
        (list, [1, 2, 3]),
        (dict, {"a": 1}),
    ],
)
def test_noop_converter_returns_same_object(registry: ConverterRegistry, tp, value) -> None:
    conv = NoOpConverterFactory().converter(tp, tp, registry)
    assert conv is not None
    assert conv.convert(value) is value


@pytest.mark.parametrize(
    ("tp", "value"),
    [
        (int, "hello"),
        (str, 42),
        (float, True),
        (bool, None),
        (type(None), 3.14),
        (list, {"a": 1}),
        (dict, [1, 2, 3]),
    ],
)
def test_noop_converter_raises_typeerror_on_value_not_matching_type(tp, value) -> None:
    conv = NoOpConverter(tp)
    with pytest.raises(TypeMismatchError) as exc_info:
        conv.convert(value)
    # Verify the exception contains useful context
    assert exc_info.value.source is value
    assert exc_info.value.target_type is tp
