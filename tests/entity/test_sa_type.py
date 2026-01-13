"""Tests for SAType utility."""

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import MetaData
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.sa_type import SAType


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class Track(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "sa_type_track"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    duration: Annotated[int, mapped_column()]


class Artist(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "sa_type_artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


def test_satype_returns_sqlalchemy_type():
    """SAType[Entity] returns Entity.__sqlalchemy_type__."""
    assert SAType[Track] is Track.__sqlalchemy_type__
    assert SAType[Artist] is Artist.__sqlalchemy_type__


def test_satype_column_access():
    """SAType[Entity].column returns the SA column attribute."""
    # Access columns via SAType
    track_id = SAType[Track].id
    track_name = SAType[Track].name

    # Should be the same as direct access
    assert track_id is Track.__sqlalchemy_type__.id
    assert track_name is Track.__sqlalchemy_type__.name


def test_satype_multiple_entities():
    """SAType works with multiple different entities."""
    # Each entity gets its own SA type
    assert SAType[Track] is not SAType[Artist]

    # Column names are correct
    assert hasattr(SAType[Track], "duration")
    assert not hasattr(SAType[Artist], "duration")


def test_satype_can_instantiate():
    """SAType[Entity] returns a type that can be instantiated."""
    track_id = uuid4()
    sa_model = SAType[Track](id=track_id, name="Test Song", duration=180)

    assert sa_model.id == track_id
    assert sa_model.name == "Test Song"
    assert sa_model.duration == 180


def test_satype_automodel_accessible():
    """__sqlalchemy_automodel__ is accessible and same as __sqlalchemy_type__ by default."""
    # By default, __sqlalchemy_type__ returns __sqlalchemy_automodel__
    assert Track.__sqlalchemy_automodel__ is Track.__sqlalchemy_type__
    assert Artist.__sqlalchemy_automodel__ is Artist.__sqlalchemy_type__
