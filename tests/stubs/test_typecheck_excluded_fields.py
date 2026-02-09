"""Tests that excluded fields are omitted from generated stubs."""

from textwrap import dedent

import pytest

from tests.stubs.conftest import run_typechecker


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_excluded_field_has_correct_types(checker, stub_dir):
    """Excluded fields don't appear on SA model but included fields do."""
    code = dedent("""\
    from typing import assert_type, TypeVar
    from tests.stubs.sample_models import EntityWithExcludedField
    from sqlcrucible.entity.sa_type import SAType
    from uuid import UUID

    T = TypeVar("T")
    def cast_to(cls: type[T], obj: object) -> T:
        return obj  # type: ignore

    sa_entity = cast_to(SAType[EntityWithExcludedField], object())

    # These fields should exist and have correct types
    assert_type(sa_entity.id, UUID)
    assert_type(sa_entity.name, str)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_excluded_field_not_on_sa_model(checker, stub_dir):
    """Accessing excluded field on SA model fails type checking."""
    code = dedent("""\
    from tests.stubs.sample_models import EntityWithExcludedField
    from sqlcrucible.entity.sa_type import SAType

    # pydantic_only_field should NOT exist on the SA model
    x = SAType[EntityWithExcludedField].pydantic_only_field
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode != 0, f"{checker} should have failed for excluded field access"
    assert "pydantic_only_field" in output
