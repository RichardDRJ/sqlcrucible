"""Tests that column access on generated stubs is type-correct."""

from tests.stubs.conftest import typecheck


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[SimpleTrack], object())

    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.title, str)
    assert_type(sa_entity.duration_seconds, int)
""")
def test_valid_column_access_passes(typecheck_outcome):
    """Accessing valid columns passes type checking via SAType."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType

    x = SAType[SimpleTrack].nonexistent_column
""")
def test_invalid_column_access_fails(typecheck_outcome):
    """Accessing non-existent columns fails type checking."""
    typecheck_outcome.assert_error()


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import Dog
    from sqlcrucible.entity.sa_type import SAType
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[Dog], object())

    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.name, str)
    assert_type(sa_entity.bones_chewed, int | None)
    assert_type(sa_entity.type, str)
""")
def test_inheritance_columns_accessible(typecheck_outcome):
    """Inherited columns are accessible on child types."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubConcreteChild
    from sqlcrucible.entity.sa_type import SAType
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[StubConcreteChild], object())

    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.own_field, int)
    assert_type(sa_entity.shared_name, str)
""")
def test_abstract_parent_columns_accessible_on_concrete_child(typecheck_outcome):
    """Fields defined on an abstract parent are accessible via SAType on the concrete child."""
    typecheck_outcome.assert_ok()
