"""Decomposing a composite-backed field into its underlying columns."""

from __future__ import annotations

from uuid import uuid4

from sqlcrucible.entity.sa_type import SAType

from tests.entity.composite.conftest import Money, NullableProduct, Product


def test_to_column_dict_decomposes_composite_into_underlying_columns():
    """A ``Money`` value produces two columns — ``price_amount`` and
    ``price_currency`` — each carrying the value the composite would
    decompose into. The composite attribute name itself never appears
    in the column dict, since there is no ``price`` column on the
    underlying table."""
    product = Product(name="Book", price=Money(amount=1500, currency="GBP"))
    column_dict = product.to_column_dict()
    assert column_dict["price_amount"] == 1500
    assert column_dict["price_currency"] == "GBP"
    assert "price" not in column_dict


def test_to_column_dict_includes_plain_columns_alongside_composites():
    pid = uuid4()
    product = Product(id=pid, name="Book", price=Money(amount=1500, currency="GBP"))
    column_dict = product.to_column_dict()
    assert column_dict["id"] == pid
    assert column_dict["name"] == "Book"


def test_to_column_dict_keys_match_underlying_table_columns():
    """The flat dict's key set is exactly the leaf table's column names —
    every key is a real column we can hand to a Core-level insert."""
    product = Product(name="Book", price=Money(amount=1500, currency="GBP"))
    column_dict = product.to_column_dict()
    table = SAType[Product].__table__
    assert set(column_dict.keys()) == {col.name for col in table.columns}


def test_to_column_dict_handles_none_valued_composite():
    """A nullable composite with a ``None`` value emits ``None`` for
    every underlying column. This keeps the dict's shape stable across
    rows, which matters for a multi-row Core-level insert batch."""
    product = NullableProduct(name="Free Book", price=None)
    column_dict = product.to_column_dict()
    assert column_dict["price_amount"] is None
    assert column_dict["price_currency"] is None
