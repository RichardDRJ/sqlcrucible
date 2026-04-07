"""Internal metadata structures for entity field definitions."""

from __future__ import annotations
from sqlalchemy.util import partial
from sqlcrucible._types.forward_refs import resolve_forward_refs
from collections.abc import Callable
from enum import Enum, auto
from functools import cached_property

import typing
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, get_args, get_origin, ForwardRef

import sqlalchemy.orm
from sqlalchemy.orm import ORMDescriptor

from sqlcrucible.conversion.registry import Converter
from sqlcrucible.entity.annotations import (
    ConvertFromSAWith,
    ConvertToSAWith,
    SQLAlchemyField,
    ExcludeSAField,
)


@dataclass(frozen=True, slots=True)
class AnnotationMetadata:
    """Metadata extracted from Annotated[] type arguments.

    This is an intermediate representation used during type annotation processing
    to separate SQLCrucible-specific markers from other annotations.
    """

    fields: list[SQLAlchemyField]
    """SQLAlchemyField configurations found in annotations."""

    from_sa_converter: Converter | None
    """Custom converter for SA → entity direction."""

    to_sa_converter: Converter | None
    """Custom converter for entity → SA direction."""

    should_exclude: bool | None
    """Whether the field should be excluded from the SA model."""

    other_annotations: list[Any]
    """Non-SQLCrucible annotations to preserve (e.g., Pydantic Field metadata)."""


def _extract_annotation_metadata(annotations: tuple[Any, ...]) -> AnnotationMetadata:
    """Extract SQLCrucible metadata from Annotated[] arguments.

    Processes annotation arguments to separate SQLCrucible-specific markers
    (SQLAlchemyField, converters, ExcludeSAField) from other annotations
    that should be preserved.

    Args:
        annotations: The metadata arguments from an Annotated[] type.

    Returns:
        AnnotationMetadata containing categorized annotation data.
    """
    fields: list[SQLAlchemyField] = []
    from_sa_converter: Converter | None = None
    to_sa_converter: Converter | None = None
    other_annotations: list[Any] = []
    should_exclude: bool | None = None

    for arg in annotations:
        if isinstance(arg, SQLAlchemyField):
            fields.append(arg)
        elif isinstance(arg, ORMDescriptor):
            # ORM descriptors (mapped_column, relationship, hybrid_property, etc.)
            # in annotations become class attributes on the SA model
            fields.append(SQLAlchemyField(attr=arg))
        elif isinstance(arg, ConvertFromSAWith):
            from_sa_converter = arg.converter
        elif isinstance(arg, ConvertToSAWith):
            to_sa_converter = arg.converter
        elif isinstance(arg, ExcludeSAField):
            should_exclude = arg.value
        else:
            # Preserve non-SQLCrucible annotations (e.g., Pydantic Field metadata)
            other_annotations.append(arg)

    return AnnotationMetadata(
        fields=fields,
        from_sa_converter=from_sa_converter,
        to_sa_converter=to_sa_converter,
        should_exclude=should_exclude,
        other_annotations=other_annotations,
    )


@dataclass(frozen=True, slots=True)
class ConcreteCanonicalisedTypeform:
    """Fully resolved representation of a type annotation."""

    tp: Any
    field: SQLAlchemyField | None
    from_sa_converter: Converter | None = None
    to_sa_converter: Converter | None = None
    should_exclude: bool | None = None

    def resolve(self) -> ConcreteCanonicalisedTypeform:
        return self

    def map(
        self, fn: Callable[[ConcreteCanonicalisedTypeform], ConcreteCanonicalisedTypeform]
    ) -> CanonicalisedTypeform:
        return fn(self)


class LazyCanonicalisedTypeform:
    """Deferred representation wrapping a supplier that produces a concrete typeform."""

    __slots__ = ["_supplier", "_resolved"]

    def __init__(self, supplier: Callable[[], CanonicalisedTypeform]) -> None:
        self._supplier = supplier

    def resolve(self) -> ConcreteCanonicalisedTypeform:
        if not hasattr(self, "_resolved"):
            result = self._supplier()
            # Unwrap if the supplier returned another lazy
            while isinstance(result, LazyCanonicalisedTypeform):
                result = result.resolve()
            self._resolved = result
        return self._resolved

    def map(
        self, fn: Callable[[ConcreteCanonicalisedTypeform], ConcreteCanonicalisedTypeform]
    ) -> CanonicalisedTypeform:
        return LazyCanonicalisedTypeform(lambda: fn(self.resolve()))


CanonicalisedTypeform = ConcreteCanonicalisedTypeform | LazyCanonicalisedTypeform


def _contains_forward_ref(tp: Any) -> bool:
    """Check if any type arguments contain forward references (recursively)."""
    return isinstance(tp, (str, ForwardRef)) or any(
        _contains_forward_ref(inner) for inner in get_args(tp)
    )


def canonicalise_typeform(owner: Any, typeform: Any) -> CanonicalisedTypeform:
    """Process a type annotation to extract SQLAlchemy mapping information.

    Recursively unwraps type annotations to extract the base type,
    SQLAlchemyField configurations, custom converters, and exclusion markers.

    Supported type forms:
        - Annotated[T, ...]: Extracts metadata from annotations, recurses on T
        - Mapped[T]: SQLAlchemy's Mapped wrapper, recurses on T
        - str/ForwardRef: Deferred resolution via LazyCanonicalisedTypeform
        - Any other type: Returns as-is with no field configuration

    Args:
        owner: The class that owns the annotation (for forward ref resolution)
        typeform: The type annotation to process

    Returns:
        A CanonicalisedTypeform containing the extracted base type,
        merged field configuration, and any custom converters.
    """
    match get_origin(typeform), get_args(typeform):
        # Annotated[T, metadata...] - extract SQLCrucible metadata from annotations
        case typing.Annotated, (tp, *annotations):
            # Extract and categorize SQLCrucible-specific metadata
            meta = _extract_annotation_metadata(tuple(annotations))

            # Recurse into the inner type to handle nested Annotated/Mapped
            inner = canonicalise_typeform(owner, tp)

            return inner.map(partial(_merge_annotated, meta=meta))

        # Mapped[T] - SQLAlchemy's type wrapper, unwrap and recurse
        case sqlalchemy.orm.Mapped, (tp):
            return canonicalise_typeform(owner, tp)

        # ClassVar - class-level annotation, not an instance field
        case _ if (get_origin(typeform) or typeform) is ClassVar:
            return ConcreteCanonicalisedTypeform(tp=typeform, field=None, should_exclude=True)

        # Forward ref or parameterized type with forward refs in args (e.g. list["Employee"])
        case _ if _contains_forward_ref(typeform):

            def _resolve_parameterized() -> CanonicalisedTypeform:
                tp = resolve_forward_refs(typeform, owner)
                return canonicalise_typeform(owner, tp)

            return LazyCanonicalisedTypeform(supplier=_resolve_parameterized)

        # Plain type (str, int, CustomClass, etc.) - no unwrapping needed
        case _:
            return ConcreteCanonicalisedTypeform(tp=typeform, field=None)


def _merge_annotated(
    inner: ConcreteCanonicalisedTypeform,
    meta: AnnotationMetadata,
) -> ConcreteCanonicalisedTypeform:
    """Merge annotation metadata with an inner resolved typeform."""
    fields = [it for it in (inner.field, *meta.fields) if it]
    field = SQLAlchemyField.merge_all(*fields)
    base_tp = inner.tp
    source_tp = Annotated[base_tp, *meta.other_annotations] if meta.other_annotations else base_tp
    return ConcreteCanonicalisedTypeform(
        tp=source_tp,
        field=field,
        from_sa_converter=meta.from_sa_converter,
        to_sa_converter=meta.to_sa_converter,
        should_exclude=meta.should_exclude,
    )


class ConversionStrategy(Enum):
    """How a field's value is obtained during entity conversion."""

    EAGER = auto()
    """Converted during from_sa_model()/to_sa_model()."""

    DEFERRED = auto()
    """Loaded on-demand from SA model via descriptor (readonly_field)."""


@dataclass
class SQLCrucibleField:
    """A registered field with its canonical type and conversion strategy.

    Exposes resolved mapping properties (source_tp, mapped_name, etc.) via
    cached properties that resolve the typeform and merge field metadata on
    first access.
    """

    source_name: str
    typeform: CanonicalisedTypeform
    conversion_strategy: ConversionStrategy

    @cached_property
    def _resolved(self) -> ConcreteCanonicalisedTypeform:
        return self.typeform.resolve()

    @cached_property
    def _merged_field(self) -> SQLAlchemyField:
        return SQLAlchemyField.merge_all(self._resolved.field, SQLAlchemyField())

    @property
    def excluded(self) -> bool:
        return self._resolved.should_exclude or False

    @property
    def source_tp(self) -> Any:
        return self._resolved.tp

    @property
    def mapped_name(self) -> str:
        return self._merged_field.name or self.source_name

    @property
    def mapped_tp(self) -> Any | None:
        return self._merged_field.tp

    @property
    def mapped_attr(self) -> ORMDescriptor[Any] | None:
        return self._merged_field.attr

    @property
    def from_sa_converter(self) -> Converter | None:
        return self._resolved.from_sa_converter

    @property
    def to_sa_converter(self) -> Converter | None:
        return self._resolved.to_sa_converter
