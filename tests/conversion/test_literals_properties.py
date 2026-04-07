"""Property-based tests for the Literal converter.

These tests supplement the parametrized tests in test_literals.py by verifying
algebraic properties (subset matching, identity conversion, safe_convert
rejection) over a much wider input space using Hypothesis.
"""

from hypothesis import given

from sqlcrucible.conversion.exceptions import TypeMismatchError
from sqlcrucible.conversion.literals import LiteralConverter, LiteralConverterFactory

from tests.strategies import (
    literal_non_subset_pair,
    literal_subset_pair,
    literal_values,
    make_literal_type,
)

import pytest


@given(data=literal_subset_pair())
def test_factory_matches_when_source_is_subset(data):
    source_values, target_values = data
    source_tp = make_literal_type(source_values)
    target_tp = make_literal_type(target_values)

    factory = LiteralConverterFactory()
    assert factory.matches(source_tp, target_tp)


@given(data=literal_non_subset_pair())
def test_factory_does_not_match_when_source_is_not_subset(data):
    source_values, target_values = data
    source_tp = make_literal_type(source_values)
    target_tp = make_literal_type(target_values)

    factory = LiteralConverterFactory()
    assert not factory.matches(source_tp, target_tp)


@given(values=literal_values())
def test_reflexivity(values):
    tp = make_literal_type(values)

    factory = LiteralConverterFactory()
    assert factory.matches(tp, tp)


@given(data=literal_subset_pair())
def test_convert_is_identity(data):
    source_values, target_values = data
    target_tp = make_literal_type(target_values)

    converter = LiteralConverter(target_tp)
    for value in source_values:
        assert converter.convert(value) is value


@given(data=literal_subset_pair())
def test_safe_convert_accepts_subset_values(data):
    source_values, target_values = data
    target_tp = make_literal_type(target_values)

    converter = LiteralConverter(target_tp)
    for value in source_values:
        assert converter.safe_convert(value) is value


@given(data=literal_non_subset_pair())
def test_safe_convert_rejects_values_not_in_target(data):
    source_values, target_values = data
    target_tp = make_literal_type(target_values)
    extra_values = source_values - target_values

    converter = LiteralConverter(target_tp)
    for value in extra_values:
        with pytest.raises(TypeMismatchError):
            converter.safe_convert(value)
