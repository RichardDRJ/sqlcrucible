"""Tests that verify generated stubs are type-correct using pyright and ty."""

from textwrap import dedent

import subprocess
import tempfile
from pathlib import Path

import pytest

from sqlcrucible.stubs import generate_stubs_for_module


def run_typechecker(
    checker: str,
    code: str,
    stub_dir: Path,
) -> tuple[int, str]:
    """Run a type checker on code string with stubs configured.

    Args:
        checker: Type checker to use ("pyright" or "ty")
        code: Python code to check
        stub_dir: Path to generated stubs
    """
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        test_file = tmppath / "test_code.py"
        test_file.write_text(code)

        if checker == "pyright":
            config = tmppath / "pyrightconfig.json"
            config_data: dict[str, str] = {"stubPath": str(stub_dir)}
            config.write_text(json.dumps(config_data))
            cmd = ["pyright", str(test_file)]
        elif checker == "ty":
            # ty doesn't follow .pth files, so we need explicit search paths.
            # Stubs use namespace packages (no __init__.pyi for existing packages)
            # so they can be searched first without shadowing.
            cmd = ["ty", "check", str(test_file)]
            cmd.extend(["--extra-search-path", str(stub_dir)])
        else:
            raise ValueError(f"Unknown checker: {checker}")

        result = subprocess.run(cmd, cwd=tmppath, capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr


@pytest.fixture(scope="module")
def stub_dir():
    """Generate stubs once per test module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stub_path = Path(tmpdir)
        generate_stubs_for_module("tests.stubs.sample_models", stub_path)
        yield stub_path


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_valid_column_access_passes(checker, stub_dir):
    """Accessing valid columns passes type checking."""
    code = dedent("""\
    from typing import assert_never, assert_type, cast, TypeVar, reveal_type
    from tests.stubs.sample_models import SimpleTrack
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    reveal_type(SimpleTrack)
    reveal_type(SimpleTrack.__sqlalchemy_type__)
    sa_entity = cast_to(SimpleTrack.__sqlalchemy_type__, object())

    reveal_type(sa_entity)

    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.title, str)
    assert_type(sa_entity.duration_seconds, int)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


# This is only run with ty for now because it's not erroring - instead it's inferring
# `nonexistent_column` to be `Unknown`
@pytest.mark.parametrize("checker", ["pyright"])
def test_invalid_column_access_fails(checker, stub_dir):
    """Accessing non-existent columns fails type checking."""

    code = dedent("""\
    from tests.stubs.sample_models import SimpleTrack

    x = SimpleTrack.__sqlalchemy_type__.nonexistent_column
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    print(output)
    assert returncode != 0, f"{checker} should have failed for invalid column"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_inheritance_columns_accessible(checker, stub_dir):
    """Inherited columns are accessible on child types."""
    code = dedent("""\
    from typing import assert_never, assert_type, cast, reveal_type, TypeVar
    from tests.stubs.sample_models import Dog
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(Dog.__sqlalchemy_type__, object())
    reveal_type(sa_entity)

    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.name, str)
    assert_type(sa_entity.bones_chewed, int | None)
    assert_type(sa_entity.type, str)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_excluded_field_has_correct_types(checker, stub_dir):
    """Excluded fields don't appear on SA model but included fields do."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import EntityWithExcludedField
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(EntityWithExcludedField.__sqlalchemy_type__, object())

    # These fields should exist and have correct types
    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.name, str)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


# Only run with pyright - ty infers Unknown for missing attributes instead of erroring
@pytest.mark.parametrize("checker", ["pyright"])
def test_excluded_field_not_on_sa_model(checker, stub_dir):
    """Accessing excluded field on SA model fails type checking."""
    code = dedent("""\
    from tests.stubs.sample_models import EntityWithExcludedField

    # pydantic_only_field should NOT exist on the SA model
    x = EntityWithExcludedField.__sqlalchemy_type__.pydantic_only_field
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode != 0, f"{checker} should have failed for excluded field access"
    assert "pydantic_only_field" in output


# =============================================================================
# Relationship stub tests
# =============================================================================


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_many_to_one_relationship_type(checker, stub_dir):
    """Many-to-one relationship field has correct scalar type."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubBook
    from sqlcrucible.generated.tests.stubs.sample_models import StubAuthorAutoModel

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    book_sa = cast_to(StubBook.__sqlalchemy_type__, object())

    # author should be the StubAuthor SA type (scalar, not list)
    assert_type(book_sa.author, StubAuthorAutoModel)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_one_to_many_relationship_type(checker, stub_dir):
    """One-to-many relationship field has correct list type."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import StubAuthor
    from sqlcrucible.generated.tests.stubs.sample_models import StubBookAutoModel

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    author_sa = cast_to(StubAuthor.__sqlalchemy_type__, object())

    # books should be a list of StubBook SA types
    assert_type(author_sa.books, list[StubBookAutoModel])
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_relationship_fields_accessible(checker, stub_dir):
    """Relationship fields are accessible on SA models."""
    code = dedent("""\
    from typing import TypeVar, reveal_type
    from tests.stubs.sample_models import StubAuthor, StubBook

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    author_sa = cast_to(StubAuthor.__sqlalchemy_type__, object())
    book_sa = cast_to(StubBook.__sqlalchemy_type__, object())

    # Both relationship fields should be accessible
    reveal_type(author_sa.books)
    reveal_type(book_sa.author)

    # Regular fields should still work
    reveal_type(author_sa.name)
    reveal_type(book_sa.title)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


# =============================================================================
# SAType accessor tests
# =============================================================================


# Only pyright - ty infers SAType[Entity] as Unknown because it hasn't got full
# support for generic protocols (https://github.com/astral-sh/ty/issues/1714)
@pytest.mark.parametrize("checker", ["pyright"])
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
