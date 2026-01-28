"""Tests for one-to-many relationships from the child side.

Pattern: Book -> Author (Book has FK to Author, Book can access Author)
This tests the many-to-one side of the relationship.
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.fields import readonly_field


metadata = MetaData()


class ChildToParentBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class AuthorForChild(ChildToParentBase):
    __sqlalchemy_params__ = {"__tablename__": "otm_author_c"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


class BookWithAuthor(ChildToParentBase):
    __sqlalchemy_params__ = {"__tablename__": "otm_book_c"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str
    author_id: Annotated[UUID, mapped_column(ForeignKey("otm_author_c.id"))]

    author = readonly_field(
        AuthorForChild,
        SQLAlchemyField(
            name="author",
            attr=relationship(lambda: AuthorForChild.__sqlalchemy_type__),
        ),
    )


def test_one_to_many_child_to_parent():
    """Book can access its Author via readonly_field."""
    author = AuthorForChild(name="Charles Dickens")
    author_sa = author.to_sa_model()

    book = BookWithAuthor(title="Great Expectations", author_id=author.id)
    book_sa = book.to_sa_model()
    book_sa.author = author_sa

    restored_book = BookWithAuthor.from_sa_model(book_sa)

    assert restored_book.author.id == author.id
    assert restored_book.author.name == author.name
