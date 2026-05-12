"""Project entity field values onto underlying SQLAlchemy columns.

The pre-existing :func:`SQLCrucibleEntity.to_sa_model` flow constructs a
fully-mapped SA instance, which means a composite-backed field enters
the picture as a single composite attribute and SA's descriptor
decomposes it into its underlying columns under the hood. That works
fine for ``session.add`` style inserts, but bulk
``insert(table).values(...)`` (Core-level) operates on the raw columns
directly — it has no view of composites.

This module exposes the same conversion machinery at the *column*
level. :func:`classify_field_converters` walks an entity's existing
to-SA converter chain and, by introspecting the SA mapper, partitions
it into:

* :class:`ColumnProjection` entries, which know which columns each
  Pydantic field maps to and how to extract their values. Plain columns
  yield a single-value tuple; composite columns yield the tuple from
  the value's ``__composite_values__`` (the standard SA composite
  protocol).

* :class:`RelationshipProjection` entries, which carry the existing
  converter so :meth:`SQLCrucibleEntity.to_sa_model` can keep handing
  child entities to the SA constructor as relationship attributes.

Composite expansion therefore relies only on SA's standard composite
protocol — no special-casing for any concrete composite type.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect

from sqlcrucible.conversion.context import ConversionContext
from sqlcrucible.conversion.registry import Converter

if TYPE_CHECKING:
    from sqlcrucible.entity.core import SQLCrucibleEntity


@dataclass(frozen=True, slots=True)
class ColumnProjection:
    """A projection from one Pydantic field to one or more SA columns.

    For a plain field, ``column_names`` is a one-tuple and the extractor
    wraps the converted value in a one-tuple.

    For a composite-backed field, ``column_names`` lists the underlying
    columns in the same order as the value's ``__composite_values__``
    tuple, and the extractor calls that protocol method to decompose
    the converted value.
    """

    source_name: str
    """Pydantic field name on the entity."""

    column_names: tuple[str, ...]
    """SA column names this field projects onto, in the order their values
    are returned by :attr:`extractor`."""

    extractor: Callable[[Any], tuple[Any, ...]]
    """Pydantic value → tuple of column values. Applies the existing
    :class:`Converter` first (so any ``ConvertToSAWith`` customisation
    is honoured), then decomposes via the composite protocol where
    applicable."""


@dataclass(frozen=True, slots=True)
class RelationshipProjection:
    """A field whose mapped attribute is a SA relationship rather than a
    column. Held aside from column projections so consumers building
    raw column dicts (for bulk Core-level inserts etc.) can ignore them."""

    source_name: str
    mapped_name: str
    converter: Converter
    target_type: Any
    """Resolved entity-side type of ``source_name`` (the converter's
    :attr:`ConversionContext.target_type`)."""


def classify_field_converters(
    cls: type[SQLCrucibleEntity],
) -> tuple[list[ColumnProjection], list[RelationshipProjection]]:
    """Partition an entity's to-SA converters into column and relationship
    projections by consulting the SA mapper.

    The ordering of column projections matches the converter chain
    (which in turn walks base classes first, then own fields), so
    callers can rely on a stable iteration order.

    Mapped attributes that don't correspond to a known mapper property
    (e.g. ``hybrid_property``, ORM-only descriptors with no underlying
    column) are emitted as :class:`RelationshipProjection` entries —
    same shape as today's :meth:`to_sa_model`, which passes them as
    kwargs to the SA constructor.
    """
    mapper = inspect(cls.__sqlalchemy_type__)
    composites = {prop.key: prop for prop in mapper.composites}
    columns = {prop.key: prop for prop in mapper.column_attrs}
    specs = list(cls.__to_sa_model_converters__())

    column_projections = [
        _composite_projection(
            spec.source_name, spec.converter, spec.target_type, composites[spec.mapped_name]
        )
        if spec.mapped_name in composites
        else _column_projection(
            spec.source_name, spec.converter, spec.target_type, columns[spec.mapped_name]
        )
        for spec in specs
        if spec.mapped_name in composites or spec.mapped_name in columns
    ]
    relationship_projections = [
        RelationshipProjection(
            source_name=spec.source_name,
            mapped_name=spec.mapped_name,
            converter=spec.converter,
            target_type=spec.target_type,
        )
        for spec in specs
        if spec.mapped_name not in composites and spec.mapped_name not in columns
    ]
    return column_projections, relationship_projections


def _column_projection(
    source_name: str, converter: Converter, target_type: Any, column_property: Any
) -> ColumnProjection:
    column_name = column_property.columns[0].name
    context = ConversionContext(target_type=target_type)

    def extract(value: Any) -> tuple[Any, ...]:
        return (converter.convert(value, context),)

    return ColumnProjection(
        source_name=source_name,
        column_names=(column_name,),
        extractor=extract,
    )


def _composite_projection(
    source_name: str, converter: Converter, target_type: Any, composite_property: Any
) -> ColumnProjection:
    # ``CompositeProperty.columns`` is empty until mapper configure-time
    # resolves them (and even then is sometimes empty); ``.props`` is
    # the ColumnProperty list whose first column is what we want.
    column_names = tuple(prop.columns[0].name for prop in composite_property.props)
    context = ConversionContext(target_type=target_type)

    def extract(value: Any) -> tuple[Any, ...]:
        if value is None:
            return (None,) * len(column_names)
        converted = converter.convert(value, context)
        if converted is None:
            return (None,) * len(column_names)
        return tuple(converted.__composite_values__())

    return ColumnProjection(
        source_name=source_name,
        column_names=column_names,
        extractor=extract,
    )
