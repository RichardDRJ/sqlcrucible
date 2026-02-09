"""Tests for generate_model_defs_for_entity."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.annotations import ExcludeSAField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.stubs.codegen import generate_model_defs_for_entity

_metadata = MetaData()


class _Base(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _metadata}


class _Parent(_Base):
    __sqlalchemy_params__ = {
        "__tablename__": "gen_model_defs_parent",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_identity": "parent"},
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    kind: Annotated[str, mapped_column(String(50))]


class _HandwrittenSAModel(_Parent.__sqlalchemy_type__):
    __mapper_args__ = {"polymorphic_identity": "middle"}


class _Middle(_Parent):
    __sqlalchemy_type__ = _HandwrittenSAModel
    kind: Annotated[str, ExcludeSAField()] = Field(default="middle")


class _Child(_Middle):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "child"}}

    tag: Annotated[str | None, mapped_column(nullable=True)] = None
    kind: Annotated[str, ExcludeSAField()] = Field(default="child")


def test_skips_custom_sa_type():
    classdefs = generate_model_defs_for_entity(_Child)
    sources = [cd.source for cd in classdefs]
    assert _HandwrittenSAModel not in sources


def test_includes_automodels_around_custom_sa_type():
    classdefs = generate_model_defs_for_entity(_Child)
    sources = [cd.source for cd in classdefs]
    assert _Child.__sqlalchemy_type__ in sources


def test_child_automodel_derives_from_custom_sa_type():
    sa_type = _Child.__sqlalchemy_type__
    assert issubclass(sa_type, _HandwrittenSAModel)
