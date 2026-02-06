"""Tests for three-way cycle relationships.

Pattern: A -> B -> C -> A (triangular cycle with back_populates)
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field
from sqlcrucible.entity.sa_type import SAType


metadata = MetaData()


class CycleBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class CycleA(CycleBase):
    __sqlalchemy_params__ = {"__tablename__": "cycle_a"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    # A -> B
    b_items = readonly_field(
        list["CycleB"],
        SQLAlchemyField(
            name="b_items",
            attr=relationship(lambda: CycleB.__sqlalchemy_type__, back_populates="a_ref"),
        ),
    )


class CycleB(CycleBase):
    __sqlalchemy_params__ = {"__tablename__": "cycle_b"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    a_id: Annotated[UUID, mapped_column(ForeignKey("cycle_a.id"))]

    # B -> A (back)
    a_ref = readonly_field(
        CycleA,
        SQLAlchemyField(
            name="a_ref",
            attr=relationship(lambda: CycleA.__sqlalchemy_type__, back_populates="b_items"),
        ),
    )

    # B -> C
    c_items = readonly_field(
        list["CycleC"],
        SQLAlchemyField(
            name="c_items",
            attr=relationship(lambda: CycleC.__sqlalchemy_type__, back_populates="b_ref"),
        ),
    )


class CycleC(CycleBase):
    __sqlalchemy_params__ = {"__tablename__": "cycle_c"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    b_id: Annotated[UUID, mapped_column(ForeignKey("cycle_b.id"))]

    # C -> B (back)
    b_ref = readonly_field(
        CycleB,
        SQLAlchemyField(
            name="b_ref",
            attr=relationship(lambda: CycleB.__sqlalchemy_type__, back_populates="c_items"),
        ),
    )


def test_three_way_cycle():
    """Three-entity cycle (A -> B -> C with back_populates) works correctly."""
    a = CycleA(name="A")
    a_sa = a.to_sa_model()

    b = CycleB(name="B", a_id=a.id)
    b_sa = b.to_sa_model()
    b_sa.a_ref = a_sa

    c = CycleC(name="C", b_id=b.id)
    c_sa = c.to_sa_model()
    c_sa.b_ref = b_sa

    # Check relationships
    assert b_sa in a_sa.b_items
    assert c_sa in b_sa.c_items
    assert b_sa.a_ref is a_sa
    assert c_sa.b_ref is b_sa

    # Conversions work
    restored_a = CycleA.from_sa_model(a_sa)
    assert len(restored_a.b_items) == 1
    assert restored_a.b_items[0].name == "B"

    restored_c = CycleC.from_sa_model(c_sa)
    assert restored_c.b_ref.a_ref.name == "A"


def test_access_order_independence():
    """Accessing entities in different orders still works."""
    # Access C first (before A or B exist)
    _ = SAType[CycleC]

    # Now create and use them
    a = CycleA(name="A")
    a_sa = a.to_sa_model()

    b = CycleB(name="B", a_id=a.id)
    b_sa = b.to_sa_model()

    c = CycleC(name="C", b_id=b.id)
    c_sa = c.to_sa_model()

    # Everything should still work
    c_sa.b_ref = b_sa
    b_sa.a_ref = a_sa

    assert c_sa.b_ref.a_ref is a_sa
