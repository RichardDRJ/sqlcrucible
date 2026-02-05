"""Tests for hybrid_property support on SQLCrucible entities."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlcrucible.entity.sa_type import SAType

from .conftest import (
    PersonWithHybridAnnotated,
    PersonWithHybridExplicit,
    PersonWithHybridLambda,
)


@pytest.mark.parametrize(
    "entity_cls",
    [PersonWithHybridExplicit, PersonWithHybridAnnotated, PersonWithHybridLambda],
    ids=["explicit", "annotated", "lambda"],
)
def test_hybrid_property_exists_on_satype(entity_cls):
    """hybrid_property is available on the generated SAType regardless of syntax."""
    sa_type = SAType[entity_cls]
    assert hasattr(sa_type, "full_name")
    assert hasattr(sa_type, "is_adult")


def test_hybrid_property_in_where_clause(hybrid_engine):
    """hybrid_property can be used in WHERE clauses."""
    sa_type = SAType[PersonWithHybridAnnotated]

    with Session(hybrid_engine) as session:
        adult = sa_type(id=uuid4(), first_name="Alice", last_name="Adult", age=30)
        child = sa_type(id=uuid4(), first_name="Bob", last_name="Child", age=10)
        session.add_all([adult, child])
        session.commit()

        adults = session.scalars(
            select(sa_type).where(sa_type.is_adult == True)  # noqa: E712
        ).all()

        assert len(adults) == 1
        assert adults[0].first_name == "Alice"


def test_hybrid_property_in_order_by(hybrid_engine):
    """Boolean hybrid_property works in ORDER BY (False < True)."""
    sa_type = SAType[PersonWithHybridAnnotated]

    with Session(hybrid_engine) as session:
        adult = sa_type(id=uuid4(), first_name="Alice", last_name="Adult", age=30)
        child = sa_type(id=uuid4(), first_name="Bob", last_name="Child", age=10)
        session.add_all([adult, child])
        session.commit()

        people = session.scalars(select(sa_type).order_by(sa_type.is_adult)).all()

        assert people[0].first_name == "Bob"
        assert people[1].first_name == "Alice"


def test_hybrid_property_value_on_instance(hybrid_engine):
    """hybrid_property returns computed value on SA instance."""
    sa_type = SAType[PersonWithHybridAnnotated]

    with Session(hybrid_engine) as session:
        person = sa_type(id=uuid4(), first_name="John", last_name="Doe", age=25)
        session.add(person)
        session.commit()

        loaded = session.scalar(select(sa_type))
        assert loaded is not None
        assert loaded.full_name == "John Doe"
        assert loaded.is_adult is True


def test_hybrid_property_roundtrip(hybrid_engine):
    """hybrid_property works with full Pydantic <-> SA roundtrip."""
    person = PersonWithHybridAnnotated(first_name="Jane", last_name="Smith", age=28)

    with Session(hybrid_engine) as session:
        session.add(person.to_sa_model())
        session.commit()

        sa_type = SAType[PersonWithHybridAnnotated]
        loaded_sa = session.scalar(select(sa_type))
        assert loaded_sa is not None

        assert loaded_sa.full_name == "Jane Smith"
        assert loaded_sa.is_adult is True

        loaded_pydantic = PersonWithHybridAnnotated.from_sa_model(loaded_sa)
        assert loaded_pydantic.first_name == "Jane"
        assert loaded_pydantic.last_name == "Smith"


def test_hybrid_not_available_on_pydantic_instance():
    """hybrid_property defined via readonly_field is NOT on Pydantic instances.

    The hybrid_property is only added to the SAType, not the Pydantic model.
    To access computed values on Pydantic instances, use @property or
    @computed_field from Pydantic instead.
    """
    person = PersonWithHybridAnnotated(first_name="John", last_name="Doe", age=25)
    assert not callable(getattr(person, "full_name", None))
