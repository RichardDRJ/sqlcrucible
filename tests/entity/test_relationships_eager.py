"""Tests for eager relationships defined without lambda wrapper.

Pattern: Relationship defined without lambda wrapper, requiring the target
entity to be defined first so __sqlalchemy_type__ can be accessed at class
definition time.
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.descriptors import readonly_field
from sqlcrucible.entity.sa_type import SAType


metadata = MetaData()


class EagerBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


# Journalist must be defined FIRST (no relationship here)
class Journalist(EagerBase):
    __sqlalchemy_params__ = {"__tablename__": "eager_journalist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


# Article has FK to Journalist and relationship WITHOUT lambda
class Article(EagerBase):
    __sqlalchemy_params__ = {"__tablename__": "eager_article"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str
    journalist_id: Annotated[UUID, mapped_column(ForeignKey("eager_journalist.id"))]

    # No lambda! Journalist.__sqlalchemy_type__ is accessed at class definition time
    journalist = readonly_field(
        Journalist,
        SQLAlchemyField(
            name="journalist",
            attr=relationship(Journalist.__sqlalchemy_type__),
        ),
    )


def test_eager_relationship_without_lambda():
    """Relationship defined without lambda works when target is defined first."""
    journalist = Journalist(name="Jane Reporter")
    journalist_sa = journalist.to_sa_model()

    article = Article(title="Breaking News", journalist_id=journalist.id)
    article_sa = article.to_sa_model()
    article_sa.journalist = journalist_sa

    restored = Article.from_sa_model(article_sa)

    assert restored.journalist.name == "Jane Reporter"
    assert restored.title == "Breaking News"


def test_eager_relationship_child_accessed_first():
    """Eager relationship works when the child (with relationship) is accessed first."""
    # Access Article's automodel first - this is the entity WITH the relationship
    _ = SAType[Article]

    # Now create instances - Journalist automodel is created during Article's creation
    journalist = Journalist(name="Bob Editor")
    journalist_sa = journalist.to_sa_model()

    article = Article(title="Editorial", journalist_id=journalist.id)
    article_sa = article.to_sa_model()
    article_sa.journalist = journalist_sa

    restored = Article.from_sa_model(article_sa)
    assert restored.journalist.name == "Bob Editor"
