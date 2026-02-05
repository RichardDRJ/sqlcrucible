from __future__ import annotations
from types import UnionType

from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    TypeVar,
    cast,
    TYPE_CHECKING,
    ForwardRef,
    get_origin,
    get_args,
    Union,
)

from sqlalchemy import inspect
from sqlalchemy.inspection import Inspectable
from sqlalchemy.orm import (
    ColumnProperty,
    RelationshipProperty,
    CompositeProperty,
    Mapper,
)
from typing_extensions import get_annotations, Format, evaluate_forward_ref

from sqlcrucible.conversion.registry import Converter
from sqlcrucible.utils.types.annotations import unwrap

if TYPE_CHECKING:
    from sqlcrucible.entity.field_metadata import SQLAlchemyFieldDefinition
    from sqlcrucible.entity.core import SQLCrucibleEntity

_T = TypeVar("_T")
_S = TypeVar("_S")
_E = TypeVar("_E", bound="SQLCrucibleEntity")


@dataclass(slots=True)
class FieldConverter(Generic[_T, _S]):
    source_name: str
    mapped_name: str
    converter: Converter[_S, _T]


def get_from_sa_model_converter(cls: type[_E], field_def: SQLAlchemyFieldDefinition) -> Converter:
    if field_def.from_sa_converter:
        return field_def.from_sa_converter

    source_tp = field_def.source_tp
    mapped_tp = _get_sa_field_type(cls, field_def)
    result = cls.__converter_registry__.resolve(mapped_tp, source_tp)
    if result is None:
        raise TypeError(
            f"No converter found for field '{field_def.source_name}' in {cls.__name__}: "
            f"cannot convert from SQLAlchemy type {mapped_tp} to entity type {source_tp}.\n"
            f"Hint: Add a custom converter using ConvertFromSAWith:\n"
            f"    {field_def.source_name}: Annotated[{source_tp}, ..., ConvertFromSAWith(lambda x: ...)]"
        )
    return result


def get_to_sa_model_converter(cls: type[_E], field_def: SQLAlchemyFieldDefinition) -> Converter:
    if field_def.to_sa_converter:
        return field_def.to_sa_converter

    source_tp = field_def.source_tp
    mapped_tp = _get_sa_field_type(cls, field_def)
    result = cls.__converter_registry__.resolve(source_tp, mapped_tp)
    if result is None:
        raise TypeError(
            f"No converter found for field '{field_def.source_name}' in {cls.__name__}: "
            f"cannot convert from entity type {source_tp} to SQLAlchemy type {mapped_tp}.\n"
            f"Hint: Add a custom converter using ConvertToSAWith:\n"
            f"    {field_def.source_name}: Annotated[{source_tp}, ..., ConvertToSAWith(lambda x: ...)]"
        )
    return result


def _get_sa_field_type(cls: type[_E], field_def: SQLAlchemyFieldDefinition) -> Any:
    if field_def.mapped_tp:
        return field_def.mapped_tp

    sqlalchemy_type = cast(Inspectable[Mapper[Any]], cls.__sqlalchemy_type__)

    annotations = get_annotations(sqlalchemy_type, eval_str=True, format=Format.VALUE)
    if (annotation := annotations.get(field_def.mapped_name)) is not None:
        evaluated = _recursively_evaluate_forward_refs(annotation, owner=cls.__sqlalchemy_type__)
        # Strip Mapped[] wrapper since converters work with the inner type
        return unwrap(evaluated)

    attrs = inspect(sqlalchemy_type).attrs
    prop = attrs.get(field_def.mapped_name)
    match prop:
        case ColumnProperty():
            return prop.columns[0].type.python_type
        case RelationshipProperty():
            entity_class = prop.entity.class_
            # For collection relationships (one-to-many, many-to-many), wrap in list
            if prop.uselist:
                return list[entity_class]
            return entity_class
        case CompositeProperty():
            return prop.composite_class
        case _:
            # Fall back to source type for descriptors like hybrid_property
            if field_def.source_tp is not None:
                return field_def.source_tp
            prop_type = type(prop).__name__ if prop is not None else "None"
            raise TypeError(
                f"Cannot determine type for field '{field_def.source_name}' in {cls.__name__}: "
                f"SQLAlchemy attribute '{field_def.mapped_name}' has unsupported property type '{prop_type}'.\n"
                f"Hint: Use SQLAlchemyField(tp=...) to explicitly specify the mapped type:\n"
                f"    {field_def.source_name}: Annotated[..., SQLAlchemyField(tp=YourType)]"
            )


def _recursively_evaluate_forward_refs(tp: Any, owner: type[object]) -> Any:
    # Handle string forward references (e.g., "Profile" or "Profile.__sqlalchemy_type__")
    if isinstance(tp, str):
        forward_ref = ForwardRef(tp)
        return evaluate_forward_ref(forward_ref, owner=owner)

    if isinstance(tp, ForwardRef):
        return evaluate_forward_ref(tp, owner=owner)

    origin = get_origin(tp)
    args = get_args(tp)

    if origin is None:
        return tp

    evaluated_args = tuple(_recursively_evaluate_forward_refs(arg, owner) for arg in args)

    # `UnionType` can't be subscripted - we need to use `Union` instead
    if origin is UnionType:
        origin = Union
    return origin[evaluated_args] if evaluated_args else tp
