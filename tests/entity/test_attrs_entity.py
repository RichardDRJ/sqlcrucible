from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from attr import define, field, validators
from sqlalchemy import ForeignKey, MetaData
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.core import SQLCrucibleEntity
from sqlcrucible.entity.sa_type import SAType
from sqlcrucible.entity.annotations import (
    ConvertFromSAWith,
    ConvertToSAWith,
    ExcludeSAField,
    SQLAlchemyField,
)
from sqlcrucible.entity.fields import readonly_field


class BaseTestEntity(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


@define(kw_only=True)
class Artist(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(factory=uuid4)
    name: Annotated[str, mapped_column()] = field()


@define(kw_only=True)
class Track(BaseTestEntity):
    __sqlalchemy_params__ = {"__tablename__": "track"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = field(factory=uuid4)
    name: Annotated[str, mapped_column()] = field()
    length: Annotated[
        timedelta,
        mapped_column(),
        SQLAlchemyField(name="length_seconds", tp=int),
        ConvertToSAWith(lambda td: td.total_seconds()),
        ConvertFromSAWith(lambda it: timedelta(seconds=it)),
    ] = field()
    notes: Annotated[str | None, mapped_column(nullable=True)] = field(default=None)

    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))] = field()

    artist = readonly_field(
        Artist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(lambda: Artist.__sqlalchemy_type__),
        ),
    )


def test_attrs_to_sa_model():
    """Attrs entity converts to SQLAlchemy model."""
    artist = Artist(name="The Beatles")
    sa_model = artist.to_sa_model()

    assert sa_model.id == artist.id
    assert sa_model.name == artist.name


def test_attrs_from_sa_model():
    """Attrs entity creates from SQLAlchemy model."""
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


def test_attrs_with_validators():
    """Attrs validators don't interfere with conversion."""

    @define
    class ValidatedEntity(SQLCrucibleEntity):
        __sqlalchemy_params__ = {"__tablename__": "attrs_validated"}
        id: Annotated[int, mapped_column(primary_key=True)] = field()
        name: Annotated[str, mapped_column()] = field(validator=validators.instance_of(str))

    entity = ValidatedEntity(id=1, name="Test")
    restored = ValidatedEntity.from_sa_model(entity.to_sa_model())

    assert restored.name == "Test"


def test_exclude_sa_field_not_on_sa_model():
    """Fields with ExcludeSAField exist on entity but not on SA model."""

    @define(kw_only=True)
    class EntityWithExcluded(BaseTestEntity):
        __sqlalchemy_params__ = {"__tablename__": "attrs_excluded_test"}
        id: Annotated[int, mapped_column(primary_key=True)] = field()
        name: Annotated[str, mapped_column()] = field()
        # This field exists on the entity but not on the SA model
        computed_tag: Annotated[str, ExcludeSAField()] = field(default="default_tag")

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

    @define(kw_only=True)
    class EntityWithExcluded(BaseTestEntity):
        __sqlalchemy_params__ = {"__tablename__": "attrs_excluded_roundtrip"}
        id: Annotated[int, mapped_column(primary_key=True)] = field()
        name: Annotated[str, mapped_column()] = field()
        excluded_field: Annotated[str, ExcludeSAField()] = field(default="default_value")

    entity = EntityWithExcluded(id=1, name="Test", excluded_field="custom_value")
    sa_model = entity.to_sa_model()
    restored = EntityWithExcluded.from_sa_model(sa_model)

    # Restored entity gets the default value since it wasn't stored
    assert restored.id == 1
    assert restored.name == "Test"
    assert restored.excluded_field == "default_value"
