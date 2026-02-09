"""Tests that SAType accessor resolves to the correct generated model."""

from textwrap import dedent

import pytest

from tests.stubs.conftest import run_typechecker


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_satype_returns_correct_type(checker, stub_dir):
    """SAType[Entity] returns the correct SQLAlchemy type."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType
    from sqlcrucible.generated.tests.stubs.sample_models import SimpleTrackAutoModel

    # SAType[SimpleTrack] should return SimpleTrackAutoModel
    assert_type(SAType[SimpleTrack], type[SimpleTrackAutoModel])
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_satype_attribute_access(checker, stub_dir):
    """SAType[Entity].attr is accepted by type checkers (no attribute error)."""
    code = dedent("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType

    # This should not raise a type error
    _ = SAType[SimpleTrack].id
    _ = SAType[SimpleTrack].title
    _ = SAType[SimpleTrack].duration_seconds
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_satype_in_select_statement(checker, stub_dir):
    """SAType can be used in SQLAlchemy select statements."""
    code = dedent("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType
    from sqlalchemy import select

    # Typical usage pattern
    stmt = select(SAType[SimpleTrack]).where(SAType[SimpleTrack].duration_seconds > 180)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_satype_resolves_abstract_entity(checker, stub_dir):
    """SAType[AbstractEntity] resolves fields defined on the abstract base."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubAbstractParent
    from sqlcrucible.entity.sa_type import SAType

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[StubAbstractParent], object())

    assert_type(sa_entity.shared_name, str)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"
