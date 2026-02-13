"""Tests for readonly_field serialisation behaviour.

Verifies how readonly_field interacts with Pydantic's model_dump(),
including exclusion by default and exposure via @computed_field.
"""

import pytest
from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field, computed_field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field


excluded_metadata = MetaData()


class ExcludedBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": excluded_metadata}


class ExcludedArtist(ExcludedBase):
    __sqlalchemy_params__ = {"__tablename__": "excluded_artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


class ExcludedTrack(ExcludedBase):
    __sqlalchemy_params__ = {"__tablename__": "excluded_track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("excluded_artist.id"))]

    artist = readonly_field(
        ExcludedArtist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(lambda: ExcludedArtist.__sqlalchemy_type__),
        ),
    )


def test_model_dump_excludes_readonly_fields():
    """readonly_field values are not included in model_dump() output."""
    artist = ExcludedArtist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = ExcludedTrack(name="Comfortably Numb", artist_id=artist.id)
    track_sa = track.to_sa_model()
    track_sa.artist = artist_sa

    restored = ExcludedTrack.from_sa_model(track_sa)
    dumped = restored.model_dump()

    assert "artist" not in dumped


wrapped_metadata = MetaData()


class WrappedBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": wrapped_metadata}


class WrappedArtist(WrappedBase):
    __sqlalchemy_params__ = {"__tablename__": "wrapped_artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


class WrappedTrack(WrappedBase):
    __sqlalchemy_params__ = {"__tablename__": "wrapped_track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("wrapped_artist.id"))]

    artist = computed_field(
        readonly_field(
            WrappedArtist,
            SQLAlchemyField(
                name="artist",
                attr=relationship(lambda: WrappedArtist.__sqlalchemy_type__),
            ),
        )
    )


def test_computed_field_wrapping_readonly_field_appears_in_model_dump():
    """A @computed_field that wraps a readonly_field appears in model_dump()."""
    artist = WrappedArtist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = WrappedTrack(name="Comfortably Numb", artist_id=artist.id)
    track_sa = track.to_sa_model()
    track_sa.artist = artist_sa

    restored = WrappedTrack.from_sa_model(track_sa)
    dumped = restored.model_dump()

    assert dumped["artist"] == {"id": artist.id, "name": "Pink Floyd"}


bidirectional_metadata = MetaData()


class BidirectionalBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": bidirectional_metadata}


class BidirectionalArtist(BidirectionalBase):
    __sqlalchemy_params__ = {"__tablename__": "bidirectional_artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    _tracks = readonly_field(
        list["BidirectionalTrack"],
        SQLAlchemyField(
            name="tracks",
            attr=relationship(
                lambda: BidirectionalTrack.__sqlalchemy_type__,
                back_populates="artist",
            ),
        ),
    )

    @computed_field
    @property
    def tracks(self) -> list["BidirectionalTrack"]:
        return self._tracks


class BidirectionalTrack(BidirectionalBase):
    __sqlalchemy_params__ = {"__tablename__": "bidirectional_track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("bidirectional_artist.id"))]

    _artist = readonly_field(
        BidirectionalArtist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(
                lambda: BidirectionalArtist.__sqlalchemy_type__,
                back_populates="tracks",
            ),
        ),
    )

    @computed_field
    @property
    def artist(self) -> BidirectionalArtist:
        return self._artist


def test_readonly_field_caches_entity_across_accesses():
    """Accessing an entity-typed readonly_field twice returns the same object."""
    artist = ExcludedArtist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = ExcludedTrack(name="Comfortably Numb", artist_id=artist.id)
    track_sa = track.to_sa_model()
    track_sa.artist = artist_sa

    restored = ExcludedTrack.from_sa_model(track_sa)
    assert restored.artist is restored.artist


def test_readonly_field_caches_list_across_accesses():
    """Accessing a list-typed readonly_field twice returns the same list object."""
    artist = BidirectionalArtist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = BidirectionalTrack(name="Comfortably Numb", artist_id=artist.id)
    track_sa = track.to_sa_model()
    artist_sa.tracks = [track_sa]

    restored = BidirectionalArtist.from_sa_model(artist_sa)
    assert restored._tracks is restored._tracks


scalar_metadata = MetaData()


class ScalarBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": scalar_metadata}


def _full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"


class ScalarPerson(ScalarBase):
    __sqlalchemy_params__ = {"__tablename__": "scalar_person"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    first_name: str
    last_name: str

    full_name = readonly_field(str, hybrid_property(_full_name))


def test_readonly_field_caches_scalar_across_accesses():
    """Accessing a scalar-typed readonly_field twice returns the same object."""
    person = ScalarPerson(first_name="David", last_name="Gilmour")
    person_sa = person.to_sa_model()

    restored = ScalarPerson.from_sa_model(person_sa)
    assert restored.full_name is restored.full_name


def test_bidirectional_computed_field_over_readonly_field_causes_recursion_error():
    """Both sides wrapping readonly_field with @computed_field causes an error on model_dump()."""
    artist = BidirectionalArtist(name="Pink Floyd")
    artist_sa = artist.to_sa_model()

    track = BidirectionalTrack(name="Comfortably Numb", artist_id=artist.id)
    track_sa = track.to_sa_model()
    artist_sa.tracks = [track_sa]

    restored = BidirectionalTrack.from_sa_model(track_sa)

    with pytest.raises(ValueError, match="Circular reference detected"):
        restored.model_dump()
