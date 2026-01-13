"""Sample models for stub generation tests."""

from sqlcrucible.entity.annotations import ExcludeSAField

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel


class StubTestBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class Animal(StubTestBase):
    """Base animal entity for inheritance testing."""

    __sqlalchemy_params__ = {
        "__tablename__": "stub_animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: Annotated[str, mapped_column()]


class Dog(Animal):
    """Dog entity for inheritance testing."""

    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "dog"}}

    bones_chewed: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")


class SimpleTrack(StubTestBase):
    """Simple track entity for basic stub testing."""

    __sqlalchemy_params__ = {"__tablename__": "stub_track"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: Annotated[str, mapped_column()]
    duration_seconds: Annotated[int, mapped_column()]


class EntityWithExcludedField(StubTestBase):
    """Entity with an excluded field for stub testing."""

    __sqlalchemy_params__ = {"__tablename__": "stub_excluded"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    # This field exists on the entity but NOT on the SA model
    pydantic_only_field: Annotated[str, ExcludeSAField()] = "default"
