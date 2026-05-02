"""Reading composite-backed fields back into entity instances."""

from __future__ import annotations

from uuid import uuid4

from sqlcrucible.entity.sa_type import SAType

from tests.entity.composite.conftest import Money, Product


def test_from_sa_model_reconstructs_entity_with_composite():
    sa_model = SAType[Product](
        id=uuid4(),
        name="Book",
        price_amount=1500,
        price_currency="GBP",
    )
    product = Product.from_sa_model(sa_model)
    assert product.price == Money(amount=1500, currency="GBP")


def test_roundtrip_through_sa_preserves_composite_value():
    pid = uuid4()
    original = Product(id=pid, name="Book", price=Money(amount=1500, currency="GBP"))
    sa_model = original.to_sa_model()
    roundtripped = Product.from_sa_model(sa_model)
    assert roundtripped.id == pid
    assert roundtripped.name == "Book"
    assert roundtripped.price == Money(amount=1500, currency="GBP")
