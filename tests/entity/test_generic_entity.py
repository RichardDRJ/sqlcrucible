"""Regression: ``SQLCrucibleEntity.__init_subclass__`` cooperates with
``typing.Generic.__init_subclass__``.

Without ``super().__init_subclass__(**kwargs)`` propagating up the MRO,
the typing machinery never gets to populate ``__parameters__`` on the
class, and Pydantic refuses to subscript the class with
"does not inherit from typing.Generic" (CPython 3.13+ even attaches a
note pointing at this exact failure mode).
"""

from typing import Annotated, Generic, TypeVar
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel, SQLCrucibleEntity
from sqlcrucible.entity.sa_type import SAType


T = TypeVar("T")
P = TypeVar("P", bound=BaseModel)


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


def test_sqlcrucible_entity_subclass_preserves_generic_parameters():
    """Subclassing both ``SQLCrucibleEntity`` and ``Generic[P]`` must
    leave ``__parameters__`` populated by ``typing.Generic``."""

    class Container(SQLCrucibleEntity, Generic[P]):
        pass

    assert getattr(Container, "__parameters__", ()) == (P,)


def test_pydantic_entity_subclass_can_be_parameterised():
    """``BaseModel`` + ``SQLCrucibleEntity`` + ``Generic[P]`` should
    accept Pydantic's ``Container[Concrete]`` subscript without
    raising 'does not inherit from typing.Generic'."""

    class Inner(BaseModel):
        x: int

    class Container(BaseTestEntity, Generic[P]):
        __sqlalchemy_params__ = {"__tablename__": "_generic_container"}

        id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
        payload: Annotated[P, mapped_column(JSONB, nullable=True)]

    Specialised = Container[Inner]
    assert Specialised.__pydantic_generic_metadata__["args"] == (Inner,)


_DB_ROUNDTRIP_METADATA = MetaData()


class _DBRoundTripBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _DB_ROUNDTRIP_METADATA}


class GenericContainer(_DBRoundTripBase, Generic[T]):
    """Generic on ``T`` purely as a Pydantic-side type parameter; the
    SA columns are concrete. Confirms ``__init_subclass__`` cooperation
    survives the auto-model + table generation path that runs when
    ``SAType[…]`` is first resolved on the generic base."""

    __sqlalchemy_params__ = {"__tablename__": "_generic_container"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    label: Annotated[str, mapped_column(nullable=False)]


@pytest.fixture
def engine():
    SAType[GenericContainer]
    engine = create_engine("sqlite:///:memory:")
    _DB_ROUNDTRIP_METADATA.create_all(engine)
    yield engine
    engine.dispose()


def test_generic_entity_persists_and_reads_back(engine):
    """A row inserted via the generic base reads back through the same
    base; the generic parameter is irrelevant to the SA layer but the
    auto-model + mapper had to be built without errors."""

    written = GenericContainer(label="hello")

    with Session(engine) as session:
        session.add(written.to_sa_model())
        session.commit()

        loaded_sa = session.scalar(select(SAType[GenericContainer]))

    assert loaded_sa is not None
    loaded = GenericContainer.from_sa_model(loaded_sa)
    assert loaded.label == "hello"
