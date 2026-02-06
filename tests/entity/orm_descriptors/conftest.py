"""Shared fixtures and model definitions for ORM descriptor tests.

SQLCrucible supports SQLAlchemy ORM descriptors via two mechanisms:
1. readonly_field() with SQLAlchemyField(attr=descriptor) for explicit control
2. Annotated[type, descriptor] syntax for concise declaration

IMPORTANT USAGE NOTES:

hybrid_property:
- Must be defined OUTSIDE the class body (as a lambda or separate function)
- Cannot use @hybrid_property decorator syntax directly on class methods
- The function receives `self` which is the SQLAlchemy model instance, not Pydantic

association_proxy:
- Provides a proxy to attributes on related objects
- The related object must be accessible via a relationship
- The proxy is read-only by default unless creator is specified

Both descriptor types:
- Are only available on the SAType, not on Pydantic instances
- Work in SQL queries (WHERE, ORDER BY, etc.)
- Must use Pydantic's ignored_types if defined as class attributes
"""

from dataclasses import field
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from pydantic import ConfigDict
from sqlalchemy import ForeignKey, MetaData, create_engine
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import ReadonlyFieldDescriptor, readonly_field
from sqlcrucible.entity.sa_type import SAType


orm_descriptor_metadata = MetaData()


class DescriptorTestBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": orm_descriptor_metadata}
    model_config = ConfigDict(ignored_types=(hybrid_property, ReadonlyFieldDescriptor))


# --- Hybrid property function definitions (must be outside class body) ---


def _full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"


def _is_adult(self) -> bool:
    return self.age >= 18


# --- Hybrid property test models ---


class PersonWithHybridExplicit(DescriptorTestBase):
    """Person using explicit descriptor argument syntax."""

    __sqlalchemy_params__ = {"__tablename__": "person_hybrid_explicit"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]
    age: Annotated[int, mapped_column()]

    # New cleaner syntax: pass descriptor directly
    full_name = readonly_field(str, hybrid_property(_full_name))
    is_adult = readonly_field(bool, hybrid_property(_is_adult))


class PersonWithHybridAnnotated(DescriptorTestBase):
    """Person using Annotated[type, hybrid_property(...)] syntax."""

    __sqlalchemy_params__ = {"__tablename__": "person_hybrid_annotated"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]
    age: Annotated[int, mapped_column()]

    full_name: Annotated[str, hybrid_property(_full_name)] = readonly_field(str)
    is_adult: Annotated[bool, hybrid_property(_is_adult)] = readonly_field(bool)


class PersonWithHybridLambda(DescriptorTestBase):
    """Person using inline lambda for hybrid_property."""

    __sqlalchemy_params__ = {"__tablename__": "person_hybrid_lambda"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]
    age: Annotated[int, mapped_column()]

    full_name: Annotated[
        str, hybrid_property(lambda self: f"{self.first_name} {self.last_name}")
    ] = readonly_field(str)
    is_adult: Annotated[bool, hybrid_property(lambda self: self.age >= 18)] = readonly_field(bool)


# --- Association proxy test models ---


class Department(DescriptorTestBase):
    __sqlalchemy_params__ = {"__tablename__": "department_assoc"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


class EmployeeWithProxy(DescriptorTestBase):
    __sqlalchemy_params__ = {"__tablename__": "employee_assoc"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    department_id: Annotated[UUID, mapped_column(ForeignKey("department_assoc.id"))]

    department = readonly_field(
        Department,
        SQLAlchemyField(
            name="department",
            attr=relationship(lambda: SAType[Department]),
        ),
    )

    department_name: Annotated[str, association_proxy("department", "name")] = readonly_field(str)


# --- Writable descriptor test models ---


def _get_writable_full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"


def _set_writable_full_name(self, value: str) -> None:
    parts = value.split(" ", 1)
    self.first_name = parts[0]
    self.last_name = parts[1] if len(parts) > 1 else ""


_writable_full_name = hybrid_property(_get_writable_full_name).setter(_set_writable_full_name)


class PersonWithWritableHybrid(DescriptorTestBase):
    """Person with a writable hybrid_property (not using readonly_field)."""

    __sqlalchemy_params__ = {"__tablename__": "person_writable_hybrid"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    full_name: Annotated[str, _writable_full_name]


class WritableProxyTarget(DescriptorTestBase):
    __sqlalchemy_params__ = {"__tablename__": "writable_proxy_target"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


class EntityWithWritableProxy(DescriptorTestBase):
    __sqlalchemy_params__ = {"__tablename__": "entity_writable_proxy"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    target_id: Annotated[UUID, mapped_column(ForeignKey("writable_proxy_target.id"))]

    target = readonly_field(
        WritableProxyTarget,
        SQLAlchemyField(
            name="target",
            attr=relationship(lambda: SAType[WritableProxyTarget]),
        ),
    )

    target_name: Annotated[
        str,
        association_proxy(
            "target",
            "name",
            creator=lambda name: SAType[WritableProxyTarget](id=uuid4(), name=name),
        ),
    ]


# --- Fixtures ---


@pytest.fixture
def hybrid_engine():
    engine = create_engine("sqlite:///:memory:")
    SAType[PersonWithHybridAnnotated].__table__.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def association_proxy_engine():
    engine = create_engine("sqlite:///:memory:")
    SAType[Department].__table__.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def writable_hybrid_engine():
    engine = create_engine("sqlite:///:memory:")
    SAType[PersonWithWritableHybrid].__table__.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def writable_proxy_engine():
    engine = create_engine("sqlite:///:memory:")
    SAType[EntityWithWritableProxy].__table__.metadata.create_all(engine)
    yield engine
    engine.dispose()
