"""Tests for relationship fields annotated with non-SA metadata.

Pattern: A parent entity has a relationship field whose annotation includes
non-SQLAlchemy metadata (e.g. access-control markers) alongside the
relationship() descriptor.
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.sa_type import SAType


metadata = MetaData()


class AnnotatedMetaBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class _ReadOnly:
    """Marker annotation that is not a SQLAlchemy or SQLCrucible type."""


READ_ONLY = _ReadOnly()


class TagAnnotated(AnnotatedMetaBase):
    __sqlalchemy_params__ = {"__tablename__": "annotated_tag"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    post_id: Annotated[UUID, mapped_column(ForeignKey("annotated_post.id"))]
    label: str


class PostAnnotated(AnnotatedMetaBase):
    __sqlalchemy_params__ = {"__tablename__": "annotated_post"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str

    tags: Annotated[
        list[TagAnnotated],
        READ_ONLY,
        relationship(
            lambda: SAType[TagAnnotated],
            foreign_keys=lambda: [SAType[TagAnnotated].post_id],
        ),
    ] = Field(default_factory=list)


def test_relationship_field_with_non_sa_annotated_metadata_roundtrips():
    """A relationship field with non-SA Annotated metadata round-trips correctly."""
    post_id = uuid4()
    tag = TagAnnotated(post_id=post_id, label="python")
    post = PostAnnotated(id=post_id, title="Hello", tags=[tag])

    restored = PostAnnotated.from_sa_model(post.to_sa_model())

    assert len(restored.tags) == 1
    assert restored.tags[0].label == "python"


def test_sa_model_annotation_for_relationship_with_annotated_metadata_uses_list():
    """The SA model annotation for an Annotated relationship field should be Mapped[list[...]]."""
    from sqlalchemy import inspect

    mapper = inspect(SAType[PostAnnotated])
    rel = next(r for r in mapper.relationships if r.key == "tags")
    assert rel.uselist is True
