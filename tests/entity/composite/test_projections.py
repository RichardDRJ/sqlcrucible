"""Inspecting the projection metadata for composite-backed fields."""

from __future__ import annotations

from tests.entity.composite.conftest import Money, Product


def test_column_projection_for_composite_lists_underlying_columns_in_order():
    [price_proj] = [
        proj for proj in Product.__column_projections__() if proj.source_name == "price"
    ]
    assert price_proj.column_names == ("price_amount", "price_currency")


def test_column_projection_for_composite_extractor_calls_composite_values():
    """The extractor honours the standard ``__composite_values__``
    protocol — no special-casing for any concrete composite type."""
    [price_proj] = [
        proj for proj in Product.__column_projections__() if proj.source_name == "price"
    ]
    assert price_proj.extractor(Money(amount=42, currency="USD")) == (42, "USD")


def test_column_projection_for_plain_field_is_a_one_tuple():
    [name_proj] = [proj for proj in Product.__column_projections__() if proj.source_name == "name"]
    assert name_proj.column_names == ("name",)
    assert name_proj.extractor("Book") == ("Book",)
