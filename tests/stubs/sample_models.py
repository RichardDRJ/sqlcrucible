"""Sample models for stub generation tests."""

from sqlcrucible.entity.annotations import ExcludeSAField, SQLAlchemyField

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData, String, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field


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


# =============================================================================
# Relationship models for stub testing
# =============================================================================

relationship_metadata = MetaData()


class RelationshipBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": relationship_metadata}


class StubAuthor(RelationshipBase):
    """Author entity with one-to-many relationship to books."""

    __sqlalchemy_params__ = {"__tablename__": "stub_author"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]

    # One-to-many: Author has many Books
    books = readonly_field(
        list["StubBook"],
        SQLAlchemyField(
            name="books",
            attr=relationship(lambda: StubBook.__sqlalchemy_type__, back_populates="author"),
        ),
    )


class StubBook(RelationshipBase):
    """Book entity with many-to-one relationship to author."""

    __sqlalchemy_params__ = {"__tablename__": "stub_book"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: Annotated[str, mapped_column()]
    author_id: Annotated[UUID, mapped_column(ForeignKey("stub_author.id"))]

    # Many-to-one: Book has one Author
    author = readonly_field(
        StubAuthor,
        SQLAlchemyField(
            name="author",
            attr=relationship(lambda: StubAuthor.__sqlalchemy_type__, back_populates="books"),
        ),
    )
