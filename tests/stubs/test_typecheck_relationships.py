"""Tests that relationship stubs have correct types."""

from tests.stubs.conftest import typecheck


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubBook
    from sqlcrucible.entity.sa_type import SAType
    from sqlcrucible.generated.tests.stubs.sample_models import StubAuthorAutoModel

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    book_sa = cast_to(SAType[StubBook], object())

    # author should be the StubAuthor SA type (scalar, not list)
    assert_type(book_sa.author, StubAuthorAutoModel)
""")
def test_many_to_one_relationship_type(typecheck_outcome):
    """Many-to-one relationship field has correct scalar type."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubAuthor
    from sqlcrucible.entity.sa_type import SAType
    from sqlcrucible.generated.tests.stubs.sample_models import StubBookAutoModel

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    author_sa = cast_to(SAType[StubAuthor], object())

    # books should be a list of StubBook SA types
    assert_type(author_sa.books, list[StubBookAutoModel])
""")
def test_one_to_many_relationship_type(typecheck_outcome):
    """One-to-many relationship field has correct list type."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from typing import TypeVar, reveal_type
    from tests.stubs.sample_models import StubAuthor, StubBook
    from sqlcrucible.entity.sa_type import SAType

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    author_sa = cast_to(SAType[StubAuthor], object())
    book_sa = cast_to(SAType[StubBook], object())

    # Both relationship fields should be accessible
    reveal_type(author_sa.books)
    reveal_type(book_sa.author)

    # Regular fields should still work
    reveal_type(author_sa.name)
    reveal_type(book_sa.title)
""")
def test_relationship_fields_accessible(typecheck_outcome):
    """Relationship fields are accessible on SA models."""
    typecheck_outcome.assert_ok()
