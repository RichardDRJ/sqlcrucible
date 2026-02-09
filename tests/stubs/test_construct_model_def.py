"""Tests for construct_model_def stub generation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.stubs.codegen import construct_model_def

_metadata = MetaData()


class _Base(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _metadata}


class _Entity(_Base):
    __sqlalchemy_params__ = {"__tablename__": "construct_model_def_entity"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


def test_includes_all_mapper_fields():
    sa_type = _Entity.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    for field_name in ("id", "name"):
        assert field_name in classdef.class_def


def test_uses_instrumented_attribute():
    sa_type = _Entity.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    assert "InstrumentedAttribute[" in classdef.class_def


def test_excludes_self_imports():
    sa_type = _Entity.__sqlalchemy_type__
    classdef = construct_model_def(sa_type)
    assert sa_type.__module__ not in classdef.imports
