from sqlcrucible.entity.annotations import ExcludeSAField
from pydantic import Field
from typing import Annotated
from uuid import UUID, uuid4

from sqlalchemy import MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.sa_type import SAType


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class Animal(BaseTestEntity):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: Annotated[str, mapped_column()]


class Dog(Animal):
    __sqlalchemy_params__ = {
        "__mapper_args__": {"polymorphic_identity": "dog"},
    }

    bones_chewed: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")


class Cat(Animal):
    __sqlalchemy_params__ = {
        "__mapper_args__": {"polymorphic_identity": "cat"},
    }

    hours_napped: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[str, ExcludeSAField()] = Field(default="cat")


def test_dog_to_sa_model():
    """Dog entity converts to SQLAlchemy model with polymorphic type."""
    dog = Dog(name="Fido", bones_chewed=42)
    sa_model = dog.to_sa_model()

    assert sa_model.id == dog.id
    assert sa_model.type == "dog"
    assert sa_model.name == "Fido"
    assert sa_model.bones_chewed == 42


def test_cat_to_sa_model():
    """Cat entity converts to SQLAlchemy model with polymorphic type."""
    cat = Cat(name="Whiskers", hours_napped=16)
    sa_model = cat.to_sa_model()

    assert sa_model.id == cat.id
    assert sa_model.type == "cat"
    assert sa_model.name == "Whiskers"
    assert sa_model.hours_napped == 16


def test_dog_from_sa_model():
    """Dog entity creates from SQLAlchemy model."""
    sa_model = SAType[Dog](id=uuid4(), type="dog", name="Rex", bones_chewed=100)
    dog = Dog.from_sa_model(sa_model)

    assert dog.id == sa_model.id
    assert dog.type == "dog"
    assert dog.name == "Rex"
    assert dog.bones_chewed == 100


def test_cat_from_sa_model():
    """Cat entity creates from SQLAlchemy model."""
    sa_model = SAType[Cat](id=uuid4(), type="cat", name="Mittens", hours_napped=20)
    cat = Cat.from_sa_model(sa_model)

    assert cat.id == sa_model.id
    assert cat.type == "cat"
    assert cat.name == "Mittens"
    assert cat.hours_napped == 20


def test_dog_roundtrip():
    """Dog entity survives round-trip conversion."""
    dog = Dog(name="Buddy", bones_chewed=7)
    sa_model = dog.to_sa_model()
    restored = Animal.from_sa_model(sa_model)
    assert isinstance(restored, Dog)

    assert restored.id == dog.id
    assert restored.type == dog.type
    assert restored.name == dog.name
    assert restored.bones_chewed == dog.bones_chewed


def test_cat_roundtrip():
    """Cat entity survives round-trip conversion."""
    cat = Cat(name="Shadow", hours_napped=12)
    sa_model = cat.to_sa_model()
    restored = Animal.from_sa_model(sa_model)
    assert isinstance(restored, Cat)

    assert restored.id == cat.id
    assert restored.type == cat.type
    assert restored.name == cat.name
    assert restored.hours_napped == cat.hours_napped


def test_dog_with_none_optional_field():
    """Dog entity with None in optional field survives round-trip."""
    dog = Dog(name="Lazy", bones_chewed=None)
    sa_model = dog.to_sa_model()
    restored = Dog.from_sa_model(sa_model)

    assert restored.bones_chewed is None


def test_cat_with_none_optional_field():
    """Cat entity with None in optional field survives round-trip."""
    cat = Cat(name="Energetic", hours_napped=None)
    sa_model = cat.to_sa_model()
    restored = Cat.from_sa_model(sa_model)

    assert restored.hours_napped is None
