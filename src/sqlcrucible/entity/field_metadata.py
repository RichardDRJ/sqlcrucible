"""Internal metadata structures for entity field definitions."""

from __future__ import annotations

import typing
from dataclasses import dataclass, replace
from typing import Annotated, Any, Self, get_args, get_origin

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
class CanonicalisedTypeform:
    """Normalized representation of a type annotation.

    This represents the result of processing a type annotation to extract
    SQLAlchemy field configuration, custom converters, and the base type.
    """

    tp: Any
    field: SQLAlchemyField | None
    from_sa_converter: Converter | None = None
    to_sa_converter: Converter | None = None
    should_exclude: bool | None = None


@dataclass(frozen=True, slots=True)
class SQLAlchemyFieldDefinition:
    """Complete specification for mapping an entity field to SQLAlchemy.

    This class captures all the information needed to map a field from the
    entity class to the corresponding SQLAlchemy model attribute, including
    custom converters and type information.

    Attributes:
        source_name: Name of the field in the entity class
        source_tp: Type of the field in the entity class
        mapped_name: Name of the attribute in the SQLAlchemy model
        mapped_tp: Type of the attribute in the SQLAlchemy model (if specified)
        mapped_attr: ORM descriptor instance (if specified), e.g. hybrid_property
        from_sa_converter: Custom converter from SA to entity (if specified)
        to_sa_converter: Custom converter from entity to SA (if specified)
        readonly: Whether this field is read-only (not included in converters)
    """

    source_name: str
    source_tp: Any

    mapped_name: str
    mapped_tp: Any | None = None

    mapped_attr: ORMDescriptor[Any] | None = None

    from_sa_converter: Converter | None = None
    to_sa_converter: Converter | None = None

    readonly: bool = False

    @classmethod
    def from_sqlalchemy_field(
        cls, source_name: str, source_tp: Any, field: SQLAlchemyField | None
    ) -> Self:
        """Create a field definition from a source type and SQLAlchemyField annotation.

        Args:
            source_name: Name of the field in the entity
            source_tp: Type annotation of the field
            field: Optional SQLAlchemyField configuration

        Returns:
            A complete SQLAlchemyFieldDefinition
        """
        canonicalised = cls._canonicalise_typeform(source_name, source_tp)
        field = SQLAlchemyField.merge_all(canonicalised.field, field or SQLAlchemyField())
        return cls.from_canonicalised(source_name, replace(canonicalised, field=field))

    @classmethod
    def from_typeform(cls, source_name: str, typeform: Any) -> Self | None:
        """Create a field definition from a type annotation.

        This is used for processing field annotations to determine if they should
        be mapped to SQLAlchemy. Returns None if the annotation doesn't contain
        SQLAlchemy mapping information.

        Args:
            source_name: Name of the field in the entity
            typeform: Type annotation to process

        Returns:
            A SQLAlchemyFieldDefinition if mapping info found, None otherwise
        """
        canonicalised = cls._canonicalise_typeform(source_name, typeform)
        if canonicalised.should_exclude:
            return None

        return cls.from_canonicalised(source_name, canonicalised)

    @classmethod
    def from_canonicalised(cls, source_name: str, canonicalised: CanonicalisedTypeform) -> Self:
        """Create a field definition from a canonicalised typeform.

        Args:
            source_name: Name of the field in the entity
            canonicalised: The canonicalised type information

        Returns:
            A complete SQLAlchemyFieldDefinition
        """
        field = SQLAlchemyField.merge_all(canonicalised.field, SQLAlchemyField())
        return cls(
            source_name=source_name,
            source_tp=canonicalised.tp,
            mapped_name=field.name or source_name,
            mapped_tp=field.tp,
            mapped_attr=field.attr,
            from_sa_converter=canonicalised.from_sa_converter,
            to_sa_converter=canonicalised.to_sa_converter,
        )

    @classmethod
    def _canonicalise_typeform(cls, source_name: str, typeform: Any) -> CanonicalisedTypeform:
        """Process a type annotation to extract SQLAlchemy mapping information.

        This method recursively unwraps type annotations to extract:
        - The base type (after stripping Annotated, Mapped wrappers)
        - SQLAlchemyField configurations (name, type, attr overrides)
        - Custom converters (ConvertFromSAWith, ConvertToSAWith)
        - Exclusion markers (ExcludeSAField)

        The method handles nested annotations by recursively processing inner types
        and merging the results. This allows annotations to be composed in any order.

        Supported type forms:
            - Annotated[T, ...]: Extracts metadata from annotations, recurses on T
            - Mapped[T]: SQLAlchemy's Mapped wrapper, recurses on T
            - Any other type: Returns as-is with no field configuration

        Example processing:
            Input:  Annotated[str, mapped_column(), SQLAlchemyField(name="db_name")]
            Output: CanonicalisedTypeform(
                tp=str,
                field=SQLAlchemyField(name="db_name"),
                ...
            )

            Input:  Annotated[timedelta, mapped_column(), ConvertToSAWith(lambda x: x.total_seconds())]
            Output: CanonicalisedTypeform(
                tp=timedelta,
                field=SQLAlchemyField(),
                to_sa_converter=FunctionConverter(...),
                ...
            )

        Args:
            source_name: Name of the field (for error messages)
            typeform: The type annotation to process

        Returns:
            A CanonicalisedTypeform containing the extracted base type,
            merged field configuration, and any custom converters.
        """
        match get_origin(typeform), get_args(typeform):
            # Case 1: Annotated[T, metadata...] - extract SQLCrucible metadata from annotations
            case typing.Annotated, (tp, *annotations):
                tp, *annotations = get_args(typeform)

                # Extract and categorize SQLCrucible-specific metadata
                meta = _extract_annotation_metadata(tuple(annotations))

                # Recurse into the inner type to handle nested Annotated/Mapped
                inner = cls._canonicalise_typeform(source_name, tp)
                fields = [it for it in (inner.field, *meta.fields) if it]

                # Merge all field configs, with later values taking precedence
                field = SQLAlchemyField.merge_all(*fields)
                # Reconstruct Annotated if there are non-SQLCrucible annotations to preserve
                source_tp = Annotated[tp, *meta.other_annotations] if meta.other_annotations else tp

                return CanonicalisedTypeform(
                    tp=source_tp,
                    field=field,
                    from_sa_converter=meta.from_sa_converter,
                    to_sa_converter=meta.to_sa_converter,
                    should_exclude=meta.should_exclude,
                )
            # Case 2: Mapped[T] - SQLAlchemy's type wrapper, unwrap and recurse
            case sqlalchemy.orm.Mapped, (tp):
                inner = cls._canonicalise_typeform(source_name, tp)
                field = SQLAlchemyField.merge_all(
                    *(it for it in [inner.field, SQLAlchemyField()] if it)
                )
                return CanonicalisedTypeform(
                    tp=inner.tp,
                    field=field,
                    from_sa_converter=inner.from_sa_converter,
                    to_sa_converter=inner.to_sa_converter,
                )

            # Case 3: Plain type (str, int, CustomClass, etc.) - no unwrapping needed
            case _:
                return CanonicalisedTypeform(tp=typeform, field=None)
