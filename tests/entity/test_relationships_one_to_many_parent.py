"""Tests for one-to-many relationships from the parent side.

Pattern: Author -> Books (Author has collection of Books via readonly_field)
This tests the one-to-many side using forward references.
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field


metadata = MetaData()


class ParentToChildBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class AuthorWithBooks(ParentToChildBase):
    __sqlalchemy_params__ = {"__tablename__": "otm_author_p"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    # Forward reference to list of Books (defined below)
    books = readonly_field(
        list["BookForAuthor"],
        SQLAlchemyField(
            name="books",
            attr=relationship(lambda: BookForAuthor.__sqlalchemy_type__),
        ),
    )


class BookForAuthor(ParentToChildBase):
    __sqlalchemy_params__ = {"__tablename__": "otm_book_p"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str
    author_id: Annotated[UUID, mapped_column(ForeignKey("otm_author_p.id"))]


def test_one_to_many_parent_to_children():
    """Author can access list of Books via readonly_field."""
    author = AuthorWithBooks(name="Jane Austen")
    author_sa = author.to_sa_model()

    book1 = BookForAuthor(title="Pride and Prejudice", author_id=author.id)
    book2 = BookForAuthor(title="Sense and Sensibility", author_id=author.id)
    book1_sa = book1.to_sa_model()
    book2_sa = book2.to_sa_model()

    author_sa.books = [book1_sa, book2_sa]

    restored_author = AuthorWithBooks.from_sa_model(author_sa)

    assert len(restored_author.books) == 2
    book_titles = {b.title for b in restored_author.books}
    assert book_titles == {"Pride and Prejudice", "Sense and Sensibility"}


def test_one_to_many_empty_list():
    """Author with no books returns empty list."""
    author = AuthorWithBooks(name="New Author")
    author_sa = author.to_sa_model()
    author_sa.books = []

    restored_author = AuthorWithBooks.from_sa_model(author_sa)

    assert restored_author.books == []


def test_one_to_many_single_child():
    """Author with single book works correctly."""
    author = AuthorWithBooks(name="Harper Lee")
    author_sa = author.to_sa_model()

    book = BookForAuthor(title="To Kill a Mockingbird", author_id=author.id)
    book_sa = book.to_sa_model()
    author_sa.books = [book_sa]

    restored_author = AuthorWithBooks.from_sa_model(author_sa)

    assert len(restored_author.books) == 1
    assert restored_author.books[0].title == "To Kill a Mockingbird"


def test_one_to_many_roundtrip():
    """Author -> Books relationship survives round-trip."""
    author = AuthorWithBooks(name="George Orwell")
    author_sa = author.to_sa_model()

    book1 = BookForAuthor(title="1984", author_id=author.id)
    book2 = BookForAuthor(title="Animal Farm", author_id=author.id)
    book1_sa = book1.to_sa_model()
    book2_sa = book2.to_sa_model()

    author_sa.books = [book1_sa, book2_sa]

    restored_author = AuthorWithBooks.from_sa_model(author_sa)

    assert restored_author.id == author.id
    assert restored_author.name == author.name
    assert len(restored_author.books) == 2
