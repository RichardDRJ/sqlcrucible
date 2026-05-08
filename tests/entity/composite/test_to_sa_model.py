"""Composite-backed fields flow through ``to_sa_model`` correctly."""

from __future__ import annotations

from tests.entity.composite.conftest import Money, NullableProduct, Product


def test_to_sa_model_with_composite_field_decomposes_correctly():
    """``to_sa_model`` flows through the column projection — its kwargs
    are the decomposed columns rather than a single composite
    attribute. SA reconstructs the composite on read."""
    product = Product(name="Book", price=Money(amount=1500, currency="GBP"))
    sa_model = product.to_sa_model()
    assert sa_model.price_amount == 1500
    assert sa_model.price_currency == "GBP"
    assert sa_model.price == Money(amount=1500, currency="GBP")


def test_to_sa_model_with_nullable_composite_set_to_none():
    product = NullableProduct(name="Free Book", price=None)
    sa_model = product.to_sa_model()
    assert sa_model.price_amount is None
    assert sa_model.price_currency is None
