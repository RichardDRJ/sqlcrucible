"""Tests that column access on generated stubs is type-correct."""

from textwrap import dedent

import pytest

from tests.stubs.conftest import run_typechecker


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_valid_column_access_passes(checker, stub_dir):
    """Accessing valid columns passes type checking via SAType."""
    code = dedent("""\
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
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_invalid_column_access_fails(checker, stub_dir):
    """Accessing non-existent columns fails type checking."""

    code = dedent("""\
    from tests.stubs.sample_models import SimpleTrack
    from sqlcrucible.entity.sa_type import SAType

    x = SAType[SimpleTrack].nonexistent_column
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    print(output)
    assert returncode != 0, f"{checker} should have failed for invalid column"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_inheritance_columns_accessible(checker, stub_dir):
    """Inherited columns are accessible on child types."""
    code = dedent("""\
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
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_abstract_parent_columns_accessible_on_concrete_child(checker, stub_dir):
    """Fields defined on an abstract parent are accessible via SAType on the concrete child."""
    code = dedent("""\
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
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"
