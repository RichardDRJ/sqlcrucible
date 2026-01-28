"""Tests for bidirectional relationships with back_populates.

Pattern: Author <-> Book with back_populates on both sides.
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


class BackPopulatesBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class BPAuthor(BackPopulatesBase):
    __sqlalchemy_params__ = {"__tablename__": "bp_author"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    books = readonly_field(
        list["BPBook"],
        SQLAlchemyField(
            name="books",
            attr=relationship(
                lambda: BPBook.__sqlalchemy_type__,
                back_populates="author",
            ),
        ),
    )


class BPBook(BackPopulatesBase):
    __sqlalchemy_params__ = {"__tablename__": "bp_book"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str
    author_id: Annotated[UUID, mapped_column(ForeignKey("bp_author.id"))]

    author = readonly_field(
        BPAuthor,
        SQLAlchemyField(
            name="author",
            attr=relationship(
                lambda: BPAuthor.__sqlalchemy_type__,
                back_populates="books",
            ),
        ),
    )


def test_back_populates_bidirectional():
    """Bidirectional relationship with back_populates works correctly."""
    author = BPAuthor(name="Jane Austen")
    author_sa = author.to_sa_model()

    book = BPBook(title="Pride and Prejudice", author_id=author.id)
    book_sa = book.to_sa_model()

    # Set up the relationship from one side
    author_sa.books = [book_sa]

    # back_populates should automatically set the reverse
    assert book_sa.author is author_sa

    # Both conversions should work
    restored_author = BPAuthor.from_sa_model(author_sa)
    restored_book = BPBook.from_sa_model(book_sa)

    assert restored_author.books[0].title == "Pride and Prejudice"
    assert restored_book.author.name == "Jane Austen"


def test_back_populates_set_from_child():
    """Setting relationship from child side propagates to parent."""
    author = BPAuthor(name="George Orwell")
    author_sa = author.to_sa_model()

    book = BPBook(title="1984", author_id=author.id)
    book_sa = book.to_sa_model()

    # Set from the child side
    book_sa.author = author_sa

    # back_populates should add to parent's collection
    assert book_sa in author_sa.books

    restored_author = BPAuthor.from_sa_model(author_sa)
    assert len(restored_author.books) == 1
    assert restored_author.books[0].title == "1984"
