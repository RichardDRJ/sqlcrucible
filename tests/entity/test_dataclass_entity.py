from uuid import uuid4, UUID
from dataclasses import field

from sqlcrucible.entity.annotations import (
    ExcludeSAField,
    SQLAlchemyField,
    ConvertToSAWith,
    ConvertFromSAWith,
)
from sqlcrucible.entity.fields import readonly_field

from datetime import timedelta

from typing import Annotated

from dataclasses import dataclass
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.core import SQLCrucibleEntity


metadata = MetaData()


class BaseTestEntity(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


@dataclass(kw_only=True)
class Artist(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]


@dataclass(kw_only=True)
class Track(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "track"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    length: Annotated[
        timedelta,
        mapped_column(),
        SQLAlchemyField(name="length_seconds", tp=int),
        ConvertToSAWith(lambda td: td.total_seconds()),
        ConvertFromSAWith(lambda it: timedelta(seconds=it)),
    ]
    notes: Annotated[str | None, mapped_column(nullable=True)] = None

    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    artist = readonly_field(
        Artist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(lambda: Artist.__sqlalchemy_type__),
        ),
    )


def test_to_sa_model_maps_fields() -> None:
    artist = Artist(name="My Chemical Romance")

    sa_artist = artist.to_sa_model()

    assert sa_artist.id == artist.id
    assert sa_artist.name == artist.name


def test_to_sa_model_uses_defined_converters() -> None:
    track = Track(
        name="Welcome to the Black Parade",
        length=timedelta(minutes=5, seconds=11),
        artist_id=uuid4(),
    )

    sa_track = track.to_sa_model()

    assert sa_track.id == track.id
    assert sa_track.name == track.name
    assert sa_track.artist_id == track.artist_id
    assert sa_track.length_seconds == track.length.total_seconds()


def test_from_sa_model_maps_fields() -> None:
    sa_artist = Artist.__sqlalchemy_type__(id=uuid4(), name="My Chemical Romance")

    artist = Artist.from_sa_model(sa_artist)

    assert sa_artist.id == artist.id
    assert sa_artist.name == artist.name


def test_from_sa_model_uses_defined_converters() -> None:
    sa_track = Track.__sqlalchemy_type__(
        id=uuid4(),
        name="Welcome to the Black Parade",
        length_seconds=5 * 60 + 11,
        artist_id=uuid4(),
    )

    track = Track.from_sa_model(sa_track)

    assert sa_track.id == track.id
    assert sa_track.name == track.name
    assert sa_track.artist_id == track.artist_id
    assert sa_track.length_seconds == track.length.total_seconds()


def test_readonly_field_converts_and_returns_sa_field():
    sa_artist = Artist.__sqlalchemy_type__(id=uuid4(), name="My Chemical Romance")
    sa_track = Track.__sqlalchemy_type__(
        id=uuid4(),
        name="Welcome to the Black Parade",
        length_seconds=5 * 60 + 11,
        artist_id=uuid4(),
        artist=sa_artist,
    )

    artist = Artist.from_sa_model(sa_artist)
    track = Track.from_sa_model(sa_track)

    assert track.artist == artist


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


def test_exclude_sa_field_not_on_sa_model():
    """Fields with ExcludeSAField exist on entity but not on SA model."""

    @dataclass(kw_only=True)
    class EntityWithExcluded(BaseTestEntity):
        __sqlalchemy_params__ = {"__tablename__": "dc_excluded_test"}
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

    @dataclass(kw_only=True)
    class EntityWithExcluded(BaseTestEntity):
        __sqlalchemy_params__ = {"__tablename__": "dc_excluded_roundtrip"}
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
