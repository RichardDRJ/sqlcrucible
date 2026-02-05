"""Tests for writable ORM descriptors (hybrid_property with setter, association_proxy with creator)."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlcrucible.entity.sa_type import SAType

from .conftest import (
    EntityWithWritableProxy,
    PersonWithWritableHybrid,
    WritableProxyTarget,
)


def test_writable_hybrid_on_sa_instance(writable_hybrid_engine):
    """hybrid_property with setter can be written to on SA instance."""
    sa_type = SAType[PersonWithWritableHybrid]

    with Session(writable_hybrid_engine) as session:
        person = sa_type(id=uuid4(), first_name="", last_name="")
        person.full_name = "John Doe"

        assert person.first_name == "John"
        assert person.last_name == "Doe"

        session.add(person)
        session.commit()

        loaded = session.scalar(select(sa_type))
        assert loaded is not None
        assert loaded.full_name == "John Doe"


def test_writable_hybrid_roundtrip(writable_hybrid_engine):
    """Writable hybrid_property participates in to/from SA model conversion."""
    person = PersonWithWritableHybrid(
        first_name="Jane",
        last_name="Smith",
        full_name="Jane Smith",
    )

    with Session(writable_hybrid_engine) as session:
        sa_model = person.to_sa_model()
        session.add(sa_model)
        session.commit()

        assert sa_model.first_name == "Jane"
        assert sa_model.last_name == "Smith"

        loaded_sa = session.scalar(select(SAType[PersonWithWritableHybrid]))
        loaded = PersonWithWritableHybrid.from_sa_model(loaded_sa)

        assert loaded.full_name == "Jane Smith"


def test_writable_proxy_on_sa_instance(writable_proxy_engine):
    """association_proxy with creator can be written to on SA instance."""
    sa_type = SAType[EntityWithWritableProxy]
    target_sa = SAType[WritableProxyTarget]

    with Session(writable_proxy_engine) as session:
        target = target_sa(id=uuid4(), name="Original")
        session.add(target)
        session.flush()

        entity = sa_type(id=uuid4(), target_id=target.id)
        session.add(entity)
        session.flush()

        assert entity.target_name == "Original"

        entity.target_name = "New Target"
        session.flush()

        assert entity.target.name == "New Target"
