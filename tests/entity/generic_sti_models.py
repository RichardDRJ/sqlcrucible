"""Sample generic single-table-inheritance hierarchy.

A music-release table whose per-kind details live in a JSON column,
typed via a generic ``Release[D]`` root. The parameterised intermediates
``Release[SingleDetails]`` / ``Release[AlbumDetails]`` add nothing of
their own at the SQLAlchemy layer, so they reuse ``Release``'s automodel;
the concrete subclasses ``Single`` / ``Album`` carry their own
``polymorphic_identity`` and get their own automodels extending
``ReleaseAutoModel`` directly.

Imported by ``test_generic_sti`` (including its stub-generation test,
which loads this module by path).
"""

from typing import Annotated, Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import JSON, MetaData, String
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator

from sqlcrucible.entity.annotations import ExcludeSAField
from sqlcrucible.entity.core import SQLCrucibleBaseModel

D = TypeVar("D", bound=BaseModel)

generic_sti_metadata = MetaData()


class PydanticJSON(TypeDecorator):
    """Stores a Pydantic model as JSON — ``model_dump`` on bind, raw
    dict on result (the consuming entity's field annotation re-validates).
    A standalone, parameter-free TypeDecorator so it's usable as the
    column type for a generic field annotated ``Mapped[D]``.

    Defines ``python_type`` (which ``JSON`` doesn't) so stub generation
    for *inherited* columns — where the subclass automodel doesn't carry
    its own annotation — has something to fall back to."""

    impl = JSON
    cache_ok = True

    @property
    def python_type(self) -> type:
        return dict

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value


class _Base(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": generic_sti_metadata}


class Release(_Base, Generic[D]):
    __sqlalchemy_params__ = {
        "__tablename__": "release",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_abstract": True},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    kind: Annotated[str, mapped_column(String, nullable=False)]
    details: Annotated[D, mapped_column(PydanticJSON(), nullable=True)]


class SingleDetails(BaseModel):
    a_side: str
    b_side: str


class AlbumDetails(BaseModel):
    track_titles: list[str]


class Single(Release[SingleDetails]):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "single"}}
    kind: Annotated[str, ExcludeSAField()] = "single"


class Album(Release[AlbumDetails]):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "album"}}
    kind: Annotated[str, ExcludeSAField()] = "album"
