"""Tests that SAType accessor resolves to the correct generated model."""

from tests.stubs.conftest import typecheck


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType
    from sqlcrucible.generated.tests.stubs.sample_models import SimpleTrackAutoModel

    # SAType[SimpleTrack] should return SimpleTrackAutoModel
    assert_type(SAType[SimpleTrack], type[SimpleTrackAutoModel])
""")
def test_satype_returns_correct_type(typecheck_outcome):
    """SAType[Entity] returns the correct SQLAlchemy type."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType

    # This should not raise a type error
    _ = SAType[SimpleTrack].id
    _ = SAType[SimpleTrack].title
    _ = SAType[SimpleTrack].duration_seconds
""")
def test_satype_attribute_access(typecheck_outcome):
    """SAType[Entity].attr is accepted by type checkers (no attribute error)."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType
    from sqlalchemy import select

    # Typical usage pattern
    stmt = select(SAType[SimpleTrack]).where(SAType[SimpleTrack].duration_seconds > 180)
""")
def test_satype_in_select_statement(typecheck_outcome):
    """SAType can be used in SQLAlchemy select statements."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubAbstractParent
    from sqlcrucible.entity.sa_type import SAType

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[StubAbstractParent], object())

    assert_type(sa_entity.shared_name, str)
""")
def test_satype_resolves_abstract_entity(typecheck_outcome):
    """SAType[AbstractEntity] resolves fields defined on the abstract base."""
    typecheck_outcome.assert_ok()
