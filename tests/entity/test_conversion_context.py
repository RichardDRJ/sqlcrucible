"""``ConvertFromSAWith`` / ``ConvertToSAWith`` callables receive a
:class:`ConversionContext` whose ``target_type`` is the *resolved* entity-side
field type — so on a concrete specialisation of a generic entity it's the
specialised type, not the declared ``TypeVar``. That holds whether the entity
is a Pydantic model (resolved via ``model_fields``) or any other backend
(resolved by substituting the type variables bound up the MRO), which is what
lets e.g. a JSON column be re-validated against the right per-subclass type.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Generic, TypeVar
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import JSON, Integer, MetaData, String
from sqlalchemy.orm import mapped_column

from sqlcrucible import ConversionContext, ConvertFromSAWith, ConvertToSAWith, ExcludeSAField
from sqlcrucible.entity.core import SQLCrucibleBaseModel, SQLCrucibleEntity
from sqlcrucible.entity.field_resolution import entity_field_type

D = TypeVar("D", bound=BaseModel)
T = TypeVar("T")

_metadata = MetaData()
_dataclass_metadata = MetaData()

#: target_type seen by the from-SA / to-SA converters, newest last.
seen_from_sa_target_types: list[Any] = []
seen_to_sa_target_types: list[Any] = []


def _meta_to_json(value: BaseModel | None, context: ConversionContext) -> Any:
    seen_to_sa_target_types.append(context.target_type)
    return None if value is None else value.model_dump(mode="json")


def _meta_from_json(value: Any, context: ConversionContext) -> Any:
    seen_from_sa_target_types.append(context.target_type)
    return None if value is None else TypeAdapter(context.target_type).validate_python(value)


def _record_to_sa(value: Any, context: ConversionContext) -> Any:
    seen_to_sa_target_types.append(context.target_type)
    return value


def _record_from_sa(value: Any, context: ConversionContext) -> Any:
    seen_from_sa_target_types.append(context.target_type)
    return value


class _MediaItemBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _metadata}


class MediaItem(_MediaItemBase, Generic[D]):
    __sqlalchemy_params__ = {
        "__tablename__": "cc_media_item",
        "__mapper_args__": {"polymorphic_on": "kind", "polymorphic_abstract": True},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    kind: Annotated[str, mapped_column(String, nullable=False)]
    meta: Annotated[
        D | None,
        mapped_column(JSON, nullable=True),
        ConvertToSAWith(_meta_to_json),
        ConvertFromSAWith(_meta_from_json),
    ] = None


class PhotoMeta(BaseModel):
    width: int
    height: int


class VideoMeta(BaseModel):
    duration_seconds: float


class Photo(MediaItem[PhotoMeta]):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "photo"}}
    kind: Annotated[str, ExcludeSAField()] = "photo"


class Video(MediaItem[VideoMeta]):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "video"}}
    kind: Annotated[str, ExcludeSAField()] = "video"


@pytest.fixture(autouse=True)
def _reset_recorders() -> None:
    seen_from_sa_target_types.clear()
    seen_to_sa_target_types.clear()


@pytest.mark.parametrize(
    ("make_item", "meta_type"),
    [
        (lambda: Photo(meta=PhotoMeta(width=4, height=3)), PhotoMeta),
        (lambda: Video(meta=VideoMeta(duration_seconds=12.5)), VideoMeta),
    ],
    ids=["photo", "video"],
)
def test_generic_subclass_converters_see_the_specialised_field_type(
    make_item: Callable[[], Photo] | Callable[[], Video], meta_type: type
) -> None:
    item = make_item()

    sa_model = item.to_sa_model()
    assert isinstance(sa_model.meta, dict)
    assert seen_to_sa_target_types[-1] == meta_type | None

    loaded = type(item).from_sa_model(sa_model)
    assert isinstance(loaded.meta, meta_type)
    assert loaded.meta == item.meta
    assert seen_from_sa_target_types[-1] == meta_type | None


def test_none_payload_round_trips_without_validation() -> None:
    loaded = Photo.from_sa_model(Photo(meta=None).to_sa_model())
    assert loaded.meta is None
    assert seen_from_sa_target_types[-1] == PhotoMeta | None


class _DataclassBase(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": _dataclass_metadata}


@dataclass(kw_only=True)
class Box(_DataclassBase, Generic[T]):
    """A non-Pydantic (dataclass) generic entity — its field type ``T`` is
    resolved by substituting the binding from a concrete subclass, with no
    help from Pydantic's ``model_fields``."""

    __sqlalchemy_params__ = {"__abstract__": True}
    value: Annotated[
        T,
        mapped_column(Integer, nullable=True),
        ConvertToSAWith(_record_to_sa),
        ConvertFromSAWith(_record_from_sa),
    ]
    siblings: Annotated[list[T], ExcludeSAField()] = field(default_factory=list)


@dataclass(kw_only=True)
class IntBox(Box[int]):
    __sqlalchemy_params__ = {"__tablename__": "cc_int_box"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)


@pytest.mark.parametrize(
    ("source_name", "expected"),
    [("value", int), ("siblings", list[int])],
    ids=["bare-typevar", "list-of-typevar"],
)
def test_typevars_resolved_for_non_pydantic_generic_subclass(
    source_name: str, expected: Any
) -> None:
    assert entity_field_type(IntBox, source_name) == expected


def test_non_pydantic_generic_converters_see_the_specialised_field_type() -> None:
    sa_model = IntBox(value=7).to_sa_model()
    assert seen_to_sa_target_types[-1] is int

    loaded = IntBox.from_sa_model(sa_model)
    assert loaded.value == 7
    assert seen_from_sa_target_types[-1] is int
