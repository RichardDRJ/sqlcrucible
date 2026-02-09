"""Tests for sa_field_type resolution."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

import pytest
from pydantic import Field
from sqlalchemy import ForeignKey, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, synonym

from sqlcrucible.entity.annotations import ExcludeSAField, SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field
from sqlcrucible.stubs.codegen import sa_field_type

# Simple entity — annotation path
_annotated_metadata = MetaData()


class _AnnotatedBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _annotated_metadata}


class _AnnotatedEntity(_AnnotatedBase):
    __sqlalchemy_params__ = {"__tablename__": "sa_field_type_annotated"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


# Single-table inheritance — column property fallback
_inheritance_metadata = MetaData()


class _InheritanceBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _inheritance_metadata}


class _Parent(_InheritanceBase):
    __sqlalchemy_params__ = {
        "__tablename__": "sa_field_type_parent",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_identity": "parent"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    kind: Annotated[str, mapped_column(String(50))]
    inherited_field: Annotated[str, mapped_column()]


class _Child(_Parent):
    """get_annotations() excludes inherited_field, forcing the column property fallback."""

    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "child"}}

    extra: Annotated[int | None, mapped_column(nullable=True)] = None
    kind: Annotated[str, ExcludeSAField()] = Field(default="child")


# Relationship pair — readonly_field annotation path
_relationship_metadata = MetaData()


class _RelBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _relationship_metadata}


class _Owner(_RelBase):
    __sqlalchemy_params__ = {"__tablename__": "sa_field_type_owner"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


class _Item(_RelBase):
    __sqlalchemy_params__ = {"__tablename__": "sa_field_type_item"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    owner_id: Annotated[UUID, mapped_column(ForeignKey("sa_field_type_owner.id"))]

    owner = readonly_field(
        _Owner,
        SQLAlchemyField(
            name="owner",
            attr=relationship(lambda: _Owner.__sqlalchemy_type__, back_populates=None),
        ),
    )


# Plain SA model with a synonym — unsupported property type
_synonym_metadata = MetaData()


class _SynonymBase(DeclarativeBase):
    metadata = _synonym_metadata


class _ModelWithSynonym(_SynonymBase):
    __tablename__ = "sa_field_type_synonym"

    id: Mapped[int] = mapped_column(primary_key=True)
    _name: Mapped[str] = mapped_column("name")
    name = synonym("_name")


def test_annotated_field_returns_mapped_type():
    sa_type = _AnnotatedEntity.__sqlalchemy_type__
    result = sa_field_type(sa_type, "name")
    assert result == Mapped[str]


def test_inherited_field_returns_python_type():
    sa_type = _Child.__sqlalchemy_type__
    result = sa_field_type(sa_type, "inherited_field")
    assert result is str


def test_readonly_relationship_returns_mapped_type():
    sa_type = _Item.__sqlalchemy_type__
    result = sa_field_type(sa_type, "owner")
    assert result == Mapped[_Owner.__sqlalchemy_type__]


def test_synonym_property_raises():
    with pytest.raises(TypeError, match="Could not determine type"):
        sa_field_type(_ModelWithSynonym, "name")
