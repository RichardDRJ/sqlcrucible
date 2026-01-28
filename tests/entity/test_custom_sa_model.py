"""Tests for customizing the generated SQLAlchemy model."""

from sqlcrucible import SAType

from typing import Annotated, ClassVar
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.utils.properties import lazyproperty


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


def user_sqlalchemy_type(cls: type["User"]):
    # Use __sqlalchemy_automodel__ as the base class for customization
    class CustomModel(cls.__sqlalchemy_automodel__):
        @hybrid_property
        def full_name(self):
            return f"{self.first_name} {self.last_name}"

    return CustomModel


class User(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "custom_user"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    __sqlalchemy_type__: ClassVar = lazyproperty(user_sqlalchemy_type)


def test_custom_model_has_hybrid_property():
    """The customized SQLAlchemy model includes the hybrid property."""
    sa_model = SAType[User](
        id=uuid4(),
        first_name="John",
        last_name="Doe",
    )

    assert sa_model.full_name == "John Doe"


def test_to_sa_model_preserves_hybrid_property():
    """Converting entity to SA model preserves access to hybrid property."""
    user = User(first_name="Jane", last_name="Smith")
    sa_model = user.to_sa_model()

    assert sa_model.first_name == "Jane"
    assert sa_model.last_name == "Smith"
    assert sa_model.full_name == "Jane Smith"


def test_from_sa_model_works_with_custom_model():
    """Converting from SA model works with customized model."""
    sa_model = SAType[User](
        id=uuid4(),
        first_name="Alice",
        last_name="Wonder",
    )

    user = User.from_sa_model(sa_model)

    assert user.first_name == "Alice"
    assert user.last_name == "Wonder"


def test_roundtrip_with_custom_model():
    """Entity → SA model → Entity roundtrip works with customized model."""
    original = User(first_name="Bob", last_name="Builder")

    sa_model = original.to_sa_model()
    assert sa_model.full_name == "Bob Builder"

    restored = User.from_sa_model(sa_model)

    assert restored.id == original.id
    assert restored.first_name == original.first_name
    assert restored.last_name == original.last_name
