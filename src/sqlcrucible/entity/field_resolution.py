from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    TypeVar,
    TYPE_CHECKING,
)

from sqlalchemy import inspect
from sqlalchemy.orm import (
    ColumnProperty,
    RelationshipProperty,
    CompositeProperty,
)
from typing_extensions import get_annotations, Format

from sqlcrucible.conversion.registry import Converter
from sqlcrucible._types.annotations import unwrap
from sqlcrucible._types.forward_refs import evaluate_forward_refs
from sqlcrucible._types.params import get_type_params_for_base

if TYPE_CHECKING:
    from sqlcrucible.entity.field_definitions import SQLCrucibleField
    from sqlcrucible.entity.core import SQLCrucibleEntity

_T = TypeVar("_T")
_S = TypeVar("_S")
_E = TypeVar("_E", bound="SQLCrucibleEntity")


@dataclass(slots=True)
class FieldConverter(Generic[_T, _S]):
    source_name: str
    mapped_name: str
    converter: Converter[_S, _T]
    target_type: Any
    """The resolved entity-side type of ``source_name`` — passed to the
    converter as :attr:`ConversionContext.target_type`. Carried per
    :class:`FieldConverter` (rather than baked into the converter) so an
    inherited converter on a concrete generic specialisation still sees the
    specialised type."""


def _substitute_type_params(tp: Any, substitution: dict[Any, Any]) -> Any:
    """Substitute type variables in ``tp`` using a ``TypeVar -> type`` map.

    Bare type variables are looked up directly; parameterised forms
    (``list[T]``, ``T | None``, ``Annotated[list[T], ...]``, ``dict[K, V]``, …)
    are re-subscripted on their free parameters — every generic-alias form,
    including ``types.UnionType``, supports that. Anything with no free
    parameters is returned unchanged. Parameters absent from ``substitution``
    are left in place (so partial specialisations stay partial)."""
    if isinstance(tp, TypeVar):
        return substitution.get(tp, tp)
    free_params: tuple[Any, ...] = getattr(tp, "__parameters__", ())
    if not free_params:
        return tp
    resolved = [substitution.get(param, param) for param in free_params]
    return tp[tuple(resolved)] if len(resolved) > 1 else tp[resolved[0]]


def entity_field_type(cls: type[SQLCrucibleEntity], source_name: str) -> Any:
    """The resolved entity-side type of ``source_name`` on ``cls``.

    For a Pydantic entity this is the substituted ``model_fields`` annotation.
    For any other entity it's the type the field was declared with, with any
    type variables bound by ``cls``'s generic specialisation substituted in —
    so a concrete specialisation of a generic entity reports the specialised
    type rather than the declared ``TypeVar``. Returns ``None`` if the field
    isn't registered."""
    model_fields = getattr(cls, "model_fields", None)
    if model_fields is not None and source_name in model_fields:
        return model_fields[source_name].annotation
    decl = cls.__sqlcrucible_fields__().get(source_name)
    if decl is None:
        return None
    owner_params = getattr(decl.owner, "__parameters__", ())
    if not owner_params or decl.owner is cls:
        return decl.source_tp
    try:
        owner_args = get_type_params_for_base(cls, decl.owner)
    except TypeError:
        return decl.source_tp
    return _substitute_type_params(decl.source_tp, dict(zip(owner_params, owner_args, strict=True)))


def get_from_sa_model_converter(cls: type[_E], field_def: SQLCrucibleField) -> Converter:
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
            f"    {field_def.source_name}: Annotated[{source_tp}, ..., ConvertFromSAWith(lambda x, ctx: ...)]"
        )
    return result


def get_to_sa_model_converter(cls: type[_E], field_def: SQLCrucibleField) -> Converter:
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
            f"    {field_def.source_name}: Annotated[{source_tp}, ..., ConvertToSAWith(lambda x, ctx: ...)]"
        )
    return result


def resolve_sa_field_type(sa_type: type, field_name: str) -> Any:
    """Determine the Python type of a SQLAlchemy model field.

    Looks up the field's type from annotations first, then falls back to
    inspecting mapper properties (columns, relationships, composites).

    Args:
        sa_type: The SQLAlchemy model class.
        field_name: The name of the field to resolve.

    Returns:
        The resolved Python type for the field, or None if the field has
        an unrecognised mapper property type.
    """
    annotations = get_annotations(sa_type, eval_str=True, format=Format.VALUE)
    if (annotation := annotations.get(field_name)) is not None:
        return evaluate_forward_refs(annotation, owner=sa_type)

    attrs = inspect(sa_type).attrs
    prop = attrs.get(field_name)
    match prop:
        case ColumnProperty():
            return prop.columns[0].type.python_type
        case RelationshipProperty():
            entity_class = prop.entity.class_
            if prop.uselist:
                return list[entity_class]
            return entity_class
        case CompositeProperty():
            return prop.composite_class
        case _:
            return None


def _get_sa_field_type(cls: type[_E], field_def: SQLCrucibleField) -> Any:
    if field_def.mapped_tp:
        return field_def.mapped_tp

    sa_type = cls.__sqlalchemy_type__
    resolved = resolve_sa_field_type(sa_type, field_def.mapped_name)
    if resolved is not None:
        # Strip Mapped[] wrapper since converters work with the inner type
        return unwrap(resolved)

    # Fall back to source type for descriptors like hybrid_property
    if field_def.source_tp is not None:
        return field_def.source_tp
    raise TypeError(
        f"Cannot determine type for field '{field_def.source_name}' in {cls.__name__}: "
        f"SQLAlchemy attribute '{field_def.mapped_name}' has unsupported property type.\n"
        f"Hint: Use SQLAlchemyField(tp=...) to explicitly specify the mapped type:\n"
        f"    {field_def.source_name}: Annotated[..., SQLAlchemyField(tp=YourType)]"
    )
