from tests.conversion.conftest import TargetItem, SourceItem

import pytest

from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.sequences import SequenceConverterFactory


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (list, set),
        (set, frozenset),
        (frozenset, list),
        (list[int], set[int]),
    ],
)
def test_sequence_factory_matches_sequence_types(source_tp, target_tp):
    sequence_factory = SequenceConverterFactory()
    assert sequence_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp"),
    [
        (dict, list),
        (str, list),
        (list, dict),
        (int, list),
    ],
)
def test_sequence_factory_does_not_match_non_sequences(source_tp, target_tp):
    sequence_factory = SequenceConverterFactory()
    assert not sequence_factory.matches(source_tp, target_tp)


@pytest.mark.parametrize(
    ("source_tp", "target_tp", "input_value", "expected_output"),
    [
        (list, set, [1, 2, 3], {1, 2, 3}),
        (set, frozenset, {1, 2, 3}, frozenset({1, 2, 3})),
        (list, set, [], set()),
        (list[int], set[int], [1, 2, 3], {1, 2, 3}),
        (list[str], set[str], ["a", "b"], {"a", "b"}),
        (
            list[SourceItem],
            set[TargetItem],
            [SourceItem(1)],
            {TargetItem(2)},
        ),
    ],
)
def test_sequence_conversion_produces_correct_type(
    registry: ConverterRegistry,
    source_tp,
    target_tp,
    input_value,
    expected_output,
):
    conv = registry.resolve(source_tp, target_tp)
    assert conv is not None
    actual_output = conv.convert(input_value)
    assert actual_output == expected_output
