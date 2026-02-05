import pytest
from uuid import uuid4, UUID

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict

from sqlcrucible.entity.annotations import (
    ExcludeSAField,
    SQLAlchemyField,
    ConvertToSAWith,
    ConvertFromSAWith,
)
from sqlcrucible.entity.fields import ReadonlyFieldDescriptor, readonly_field

from datetime import timedelta

from typing import Annotated

from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.core import SQLCrucibleEntity, SQLCrucibleBaseModel
from sqlcrucible.entity.sa_type import SAType


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class Artist(BaseTestEntity):
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


class Track(BaseTestEntity, BaseModel):
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
    __sqlalchemy_params__ = {"__tablename__": "track"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    length: Annotated[
        timedelta,
        mapped_column(),
        SQLAlchemyField(name="length_seconds", tp=int),
        ConvertToSAWith(lambda td: td.total_seconds()),
        ConvertFromSAWith(lambda it: timedelta(seconds=it)),
    ]
    notes: str | None = None

    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    artist = readonly_field(
        Artist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(lambda: Artist.__sqlalchemy_type__),
        ),
    )


def test_to_sa_model():
    """Pydantic entity converts to SQLAlchemy model."""
    artist = Artist(name="The Beatles")
    sa_model = artist.to_sa_model()

    assert sa_model.id == artist.id
    assert sa_model.name == artist.name


def test_from_sa_model():
    """Pydantic entity creates from SQLAlchemy model."""
    sa_model = SAType[Artist](id=uuid4(), name="Pink Floyd")
    artist = Artist.from_sa_model(sa_model)

    assert artist.id == sa_model.id
    assert artist.name == sa_model.name


def test_roundtrip_produces_same_model_as_original():
    """Entity → SA model → Entity preserves all field values including custom converters, unions, and relationships."""
    artist = Artist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = Track(
        name="Comfortably Numb",
        artist_id=artist.id,
        length=timedelta(minutes=6, seconds=23),
        notes="Epic guitar solo",
    )
    track_sa = track.to_sa_model()
    track_sa.artist = artist_sa

    restored_track = Track.from_sa_model(track_sa)

    assert restored_track.id == track.id
    assert restored_track.name == track.name
    assert restored_track.artist_id == track.artist_id
    assert restored_track.length == track.length
    assert restored_track.notes == track.notes
    assert restored_track.artist.id == artist.id
    assert restored_track.artist.name == artist.name


def test_roundtrip_with_none_in_union_field():
    """Entity with None value in union field survives round-trip."""
    artist = Artist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = Track(
        name="Comfortably Numb",
        artist_id=artist.id,
        length=timedelta(minutes=6, seconds=23),
        notes=None,  # Union field with None
    )
    track_sa = track.to_sa_model()
    track_sa.artist = artist_sa

    restored_track = Track.from_sa_model(track_sa)

    assert restored_track.notes is None


def test_validator_accepts_valid_data():
    """Pydantic validators work with entity conversion."""

    class ValidatedEntity(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "validated"}
        id: Annotated[int, mapped_column(primary_key=True)]
        name: Annotated[str, mapped_column()]

        @field_validator("name")
        def name_must_not_be_empty(cls, v):
            if not v.strip():
                raise ValueError("name cannot be empty")
            return v

    entity = ValidatedEntity(id=1, name="Test")
    restored = ValidatedEntity.from_sa_model(entity.to_sa_model())

    assert restored.name == "Test"


def test_validator_rejects_invalid_data():
    """Pydantic validators reject invalid data."""

    class ValidatedEntity(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "validated"}
        id: Annotated[int, mapped_column(primary_key=True)]
        name: Annotated[str, mapped_column()]

        @field_validator("name")
        def name_must_not_be_empty(cls, v):
            if not v.strip():
                raise ValueError("name cannot be empty")
            return v

    with pytest.raises(ValueError):
        ValidatedEntity(id=2, name="  ")


def test_computed_field():
    """Pydantic computed_field works with entities."""

    class EntityWithComputed(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "computed"}
        id: Annotated[int, mapped_column(primary_key=True)]
        first_name: Annotated[str, mapped_column()]
        last_name: Annotated[str, mapped_column()]

        @computed_field
        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

    entity = EntityWithComputed(id=1, first_name="John", last_name="Doe")

    assert entity.full_name == "John Doe"


def test_computed_field_survives_roundtrip():
    """Pydantic computed_field works after round-trip."""

    class EntityWithComputed(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "computed"}
        id: Annotated[int, mapped_column(primary_key=True)]
        first_name: Annotated[str, mapped_column()]
        last_name: Annotated[str, mapped_column()]

        @computed_field
        @property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

    entity = EntityWithComputed(id=1, first_name="John", last_name="Doe")
    restored = EntityWithComputed.from_sa_model(entity.to_sa_model())

    assert restored.full_name == "John Doe"


def test_exclude_sa_field_not_on_sa_model():
    """Fields with ExcludeSAField exist on entity but not on SA model."""

    class EntityWithExcluded(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "excluded_test"}
        id: Annotated[int, mapped_column(primary_key=True)]
        name: Annotated[str, mapped_column()]
        # This field exists on the entity but not on the SA model
        computed_tag: Annotated[str, ExcludeSAField()] = "default_tag"

    # Field exists on entity
    entity = EntityWithExcluded(id=1, name="Test", computed_tag="custom_tag")
    assert entity.computed_tag == "custom_tag"

    # Field does NOT exist on SA model
    sa_model = entity.to_sa_model()
    assert not hasattr(sa_model, "computed_tag")
    assert sa_model.id == 1
    assert sa_model.name == "Test"


def test_exclude_sa_field_roundtrip_uses_default():
    """Round-trip with ExcludeSAField uses the field's default value."""

    class EntityWithExcluded(SQLCrucibleEntity, BaseModel):
        __sqlalchemy_params__ = {"__tablename__": "excluded_roundtrip"}
        id: Annotated[int, mapped_column(primary_key=True)]
        name: Annotated[str, mapped_column()]
        excluded_field: Annotated[str, ExcludeSAField()] = "default_value"

    entity = EntityWithExcluded(id=1, name="Test", excluded_field="custom_value")
    sa_model = entity.to_sa_model()
    restored = EntityWithExcluded.from_sa_model(sa_model)

    # Restored entity gets the default value since it wasn't stored
    assert restored.id == 1
    assert restored.name == "Test"
    assert restored.excluded_field == "default_value"


def test_from_sa_model_raises_on_none():
    """from_sa_model raises TypeError when passed None."""
    with pytest.raises(TypeError) as exc_info:
        Artist.from_sa_model(None)
    assert "Cannot create Artist from None" in str(exc_info.value)


def test_from_sa_model_raises_on_incompatible_type():
    """from_sa_model raises ValueError when passed incompatible model."""

    class OtherEntity(BaseTestEntity):
        __sqlalchemy_params__ = {"__tablename__": "other"}
        id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
        value: Annotated[str, mapped_column()]

    other_sa = OtherEntity(value="test").to_sa_model()

    with pytest.raises(ValueError) as exc_info:
        Artist.from_sa_model(other_sa)
    assert "Cannot create Artist from" in str(exc_info.value)
