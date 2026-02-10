"""Tests that stubs do not shadow entity source types."""

from tests.stubs.conftest import typecheck


@typecheck("""\
    from typing import assert_type
    from tests.stubs.sample_models import SimpleTrack
    from uuid import UUID

    track = SimpleTrack(title="x", duration_seconds=1)
    assert_type(track.id, UUID)
    assert_type(track.title, str)
    assert_type(track.duration_seconds, int)
""")
def test_entity_fields_retain_pydantic_types(typecheck_outcome):
    """Entity field types are their declared Pydantic types, not InstrumentedAttribute."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from tests.stubs.sample_models import Animal, Dog

    dog = Dog(type="dog", name="Rex")
    animal: Animal = dog
""")
def test_entity_subclass_is_assignable_to_parent(typecheck_outcome):
    """Entity subclass instances are assignable to parent type annotations."""
    typecheck_outcome.assert_ok()


@typecheck("""\
    from tests.stubs.sample_models import SimpleTrack

    track = SimpleTrack(title="x", duration_seconds=1)
    sa = track.to_sa_model()
""")
def test_entity_to_sa_model_available(typecheck_outcome):
    """Entity methods like to_sa_model are still visible with stubs present."""
    typecheck_outcome.assert_ok()
