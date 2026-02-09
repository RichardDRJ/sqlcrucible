"""Tests that stubs do not shadow entity source types."""

from textwrap import dedent

import pytest

from tests.stubs.conftest import run_typechecker


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_entity_fields_retain_pydantic_types(checker, stub_dir):
    """Entity field types are their declared Pydantic types, not InstrumentedAttribute."""
    code = dedent("""\
    from typing import assert_type
    from tests.stubs.sample_models import SimpleTrack
    from uuid import UUID

    track = SimpleTrack(title="x", duration_seconds=1)
    assert_type(track.id, UUID)
    assert_type(track.title, str)
    assert_type(track.duration_seconds, int)
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_entity_subclass_is_assignable_to_parent(checker, stub_dir):
    """Entity subclass instances are assignable to parent type annotations."""
    code = dedent("""\
    from tests.stubs.sample_models import Animal, Dog

    dog = Dog(type="dog", name="Rex")
    animal: Animal = dog
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"


@pytest.mark.parametrize("checker", ["pyright", "ty"])
def test_entity_to_sa_model_available(checker, stub_dir):
    """Entity methods like to_sa_model are still visible with stubs present."""
    code = dedent("""\
    from tests.stubs.sample_models import SimpleTrack

    track = SimpleTrack(title="x", duration_seconds=1)
    sa = track.to_sa_model()
    """)
    returncode, output = run_typechecker(checker, code, stub_dir)
    assert returncode == 0, f"{checker} failed: {output}"
