"""Tests for the __table__ escape hatch in __sqlalchemy_params__."""

from typing import Annotated

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session

from sqlcrucible import SAType
from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel


explicit_table_metadata = MetaData()
explicit_table = Table(
    "product",
    explicit_table_metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100)),
    Column("price", Integer),
)


class Product(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__table__": explicit_table, "metadata": explicit_table_metadata}

    id: Annotated[int, SQLAlchemyField()]
    name: Annotated[str, SQLAlchemyField()]
    price: Annotated[int, SQLAlchemyField()]


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    explicit_table_metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_entity_with_explicit_table_persists_and_loads(engine):
    """Entity with explicit __table__ can be inserted and queried back."""
    product = Product(id=1, name="Widget", price=999)

    with Session(engine) as session:
        session.add(product.to_sa_model())
        session.commit()

        loaded = session.scalar(select(SAType[Product]))

    assert loaded is not None
    restored = Product.from_sa_model(loaded)

    assert restored.id == product.id
    assert restored.name == product.name
    assert restored.price == product.price


def test_explicit_table_columns_support_where_clauses(engine):
    """Columns from an explicit __table__ can be used in query filters."""
    sa_type = SAType[Product]

    with Session(engine) as session:
        session.add_all(
            [
                sa_type(id=1, name="Cheap", price=100),
                sa_type(id=2, name="Expensive", price=9000),
            ]
        )
        session.commit()

        expensive = session.scalars(select(sa_type).where(sa_type.price > 500)).all()

    assert len(expensive) == 1
    assert expensive[0].name == "Expensive"
