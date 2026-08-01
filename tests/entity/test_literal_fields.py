from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.annotations import ExcludeSAField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.sa_type import SAType


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class ShapeKind(StrEnum):
    CIRCLE = "circle"
    SQUARE = "square"


# Narrowing a discriminator to its per-subclass literal is the whole point of these
# tests, but pyright treats a mutable field's type as invariant, so any narrowing
# override trips reportIncompatibleVariableOverride. That holds however the base is
# declared - str, the full Literal union, or the enum - so the rule is suppressed on
# the two overrides rather than worked around.
class Shape(BaseTestEntity):
    __sqlalchemy_params__ = {
        "__tablename__": "shape",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_identity": "shape"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    kind: Annotated[str, mapped_column(String(50))]


class Circle(Shape):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "circle"}}

    kind: Annotated[Literal["circle"], ExcludeSAField()] = "circle"  # pyright: ignore[reportIncompatibleVariableOverride]
    radius: Annotated[int, mapped_column()]


class Square(Shape):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "square"}}

    kind: Annotated[Literal[ShapeKind.SQUARE], ExcludeSAField()] = ShapeKind.SQUARE  # pyright: ignore[reportIncompatibleVariableOverride]
    side: Annotated[int, mapped_column()]


class Tagged(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "tagged"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    tag: Annotated[Literal["a", "b"], mapped_column(String(1))] = "a"
    tags: Annotated[list[Literal["x", "y"]], ExcludeSAField()] = Field(default_factory=list)


def test_literal_str_discriminator_converts_to_sa_model():
    """A Literal[str] discriminator narrows the field without breaking conversion."""
    sa_model = Circle(radius=3).to_sa_model()

    assert sa_model.kind == "circle"
    assert sa_model.radius == 3


def test_literal_str_enum_discriminator_converts_to_sa_model():
    """A Literal[StrEnum member] discriminator behaves the same as a plain string."""
    sa_model = Square(side=4).to_sa_model()

    assert sa_model.kind == "square"
    assert sa_model.side == 4


def test_literal_str_discriminator_round_trips_from_sa_model():
    """A Literal-discriminated subclass is reconstructed from its SA model."""
    circle_id = uuid4()
    entity = Circle.from_sa_model(SAType[Circle](id=circle_id, kind="circle", radius=7))

    assert isinstance(entity, Circle)
    assert entity.id == circle_id
    assert entity.radius == 7


def test_mapped_literal_column_converts_to_sa_model():
    """A mapped (non-excluded) multi-value Literal column converts without recursing."""
    sa_model = Tagged(tag="b").to_sa_model()

    assert sa_model.tag == "b"


def test_literal_nested_in_generic_arg_converts_to_sa_model():
    """A Literal nested inside a parameterized type does not look like a forward ref."""
    entity = Tagged(tags=["x", "y"])

    assert entity.to_sa_model().id == entity.id
