"""Field descriptors for entity classes."""

from __future__ import annotations

from dataclasses import replace
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    overload,
    Self,
    get_origin,
    get_args,
    Annotated,
    cast,
)

from sqlalchemy.orm import ORMDescriptor

import sqlcrucible.entity.field_resolution
from sqlcrucible.conversion.registry import Converter
from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.field_metadata import SQLAlchemyFieldDefinition
from sqlcrucible.utils.types.forward_refs import resolve_forward_refs
from typing_extensions import get_annotations, Format

if TYPE_CHECKING:
    from sqlcrucible.entity.core import SQLCrucibleEntity

_O = TypeVar("_O", bound="SQLCrucibleEntity")
_T = TypeVar("_T")


class ReadonlyFieldDescriptor(Generic[_T, _O]):
    """Descriptor implementation for readonly_field.

    See readonly_field() function for documentation.
    """

    def __init__(self, tp: Any, sa_field: SQLAlchemyField | None = None):
        """Initialize a readonly field descriptor.

        Args:
            tp: The type of the field value (can be a type, string forward ref, or parameterized type)
            sa_field: Optional SQLAlchemyField configuration for the mapped attribute
        """
        self._tp = tp
        self._sa_field = sa_field
        self._converter: Converter[Any, _T] | None = None
        self._sa_field_info: SQLAlchemyFieldDefinition | None = None
        self._name: str | None = None
        self._owner: type[_O] | None = None

    def __set_name__(self, owner: type[_O], name: str):
        """Called when the descriptor is assigned to a class attribute.

        Registers the field definition with the entity class.
        Forward references in the type are resolved lazily when the field
        definition is actually accessed, not during class creation.

        Args:
            owner: The entity class owning this field
            name: The name of the field in the entity class
        """
        self._name = name
        self._owner = owner

        # Extract ORMDescriptor from annotation if no explicit sa_field was provided
        sa_field = self._sa_field
        if sa_field is None:
            sa_field = self._extract_sa_field_from_annotation(owner, name)

        # Register a preliminary field definition without resolving forward refs yet.
        # The type will contain unresolved forward refs, but that's OK - they'll be
        # resolved when the automodel is generated (lazily) or when the field is accessed.
        sa_field_info = SQLAlchemyFieldDefinition.from_sqlalchemy_field(
            self._name, self._tp, sa_field
        )
        # Mark as readonly so it's excluded from to/from SA model converters
        sa_field_info = replace(sa_field_info, readonly=True)
        owner.__register_sqlalchemy_field_definition__(sa_field_info)

    def _extract_sa_field_from_annotation(
        self, owner: type[_O], name: str
    ) -> SQLAlchemyField | None:
        """Extract SQLAlchemyField from the annotation if it contains an ORMDescriptor.

        This handles the case where readonly_field is used with an annotated type
        like `Annotated[str, hybrid_property(...)]` without an explicit SQLAlchemyField.
        """
        annotations = get_annotations(owner, eval_str=True, format=Format.VALUE)
        ann = annotations.get(name)
        if ann is None or get_origin(ann) is not Annotated:
            return None

        _, *metadata = get_args(ann)
        descriptor = next((arg for arg in metadata if isinstance(arg, ORMDescriptor)), None)
        return SQLAlchemyField(attr=descriptor) if descriptor else None

    @property
    def sa_field_info(self) -> SQLAlchemyFieldDefinition:
        """Get the SQLAlchemy field definition for this descriptor.

        This property resolves any forward references in the type, which requires
        all referenced classes to be defined. It's safe to call after class creation
        is complete.

        Returns:
            The field definition with resolved types

        Raises:
            RuntimeError: If accessed before the descriptor is assigned to a class
        """
        if self._sa_field_info is None:
            if self._name is None or self._owner is None:
                raise RuntimeError(
                    "Attempted to construct SQLAlchemyFieldInfo on `readonly_field` descriptor before descriptor is assigned to a field!"
                )
            # Resolve forward references using the owner class's context
            resolved_tp = resolve_forward_refs(self._tp, self._owner)
            self._sa_field_info = SQLAlchemyFieldDefinition.from_sqlalchemy_field(
                self._name, resolved_tp, self._sa_field
            )
        return self._sa_field_info

    @overload
    def __get__(self, instance: None, owner: type[_O]) -> Self: ...

    @overload
    def __get__(self, instance: _O, owner: type[_O]) -> _T: ...

    def __get__(self, instance: _O | None, owner: type[_O]) -> _T | Self:
        """Get the field value from an entity instance.

        When accessed on the class, returns the descriptor itself.
        When accessed on an instance, loads the value from the SQLAlchemy model.

        Args:
            instance: The entity instance (or None if accessed on class)
            owner: The entity class

        Returns:
            The descriptor (if accessed on class) or the field value (if on instance)

        Raises:
            RuntimeError: If the entity instance is not backed by a SQLAlchemy model
        """
        if instance is None:
            return self
        else:
            field_info = self.sa_field_info
            if self._converter is None:
                self._converter = sqlcrucible.entity.field_resolution.get_from_sa_model_converter(
                    owner, field_info
                )

            model = instance.__sa_model__
            if model is None:
                raise RuntimeError(
                    f"Cannot access readonly_field '{self._name}' on {type(instance).__name__}: "
                    f"this entity was not loaded from a SQLAlchemy model.\n"
                    f"Hint: readonly_field values are only available on entities created via "
                    f"from_sa_model(). If you need this field on manually-created entities, "
                    f"consider using a regular field instead."
                )

            return self._converter.convert(getattr(model, field_info.mapped_name))


@overload
def readonly_field(tp: type[_T]) -> _T: ...


@overload
def readonly_field(tp: type[_T], sa_field: SQLAlchemyField) -> _T: ...


@overload
def readonly_field(tp: str) -> Any: ...


@overload
def readonly_field(tp: str, sa_field: SQLAlchemyField) -> Any: ...


def readonly_field(tp: type[_T] | str, sa_field: SQLAlchemyField | None = None) -> Any:
    """Create a readonly field descriptor.

    Readonly fields are loaded from the SQLAlchemy model but cannot be set
    on the entity. They are useful for computed properties like hybrid_property
    and association_proxy.

    Args:
        tp: The type of the field value
        sa_field: Optional SQLAlchemyField configuration for the mapped attribute.
            If not provided and the field has an Annotated type with an ORMDescriptor,
            the descriptor is automatically extracted.

    Returns:
        A descriptor that loads the field value from the backing SQLAlchemy model.

    Example:
        ```python
        class Person(SQLCrucibleBaseModel):
            first_name: Annotated[str, mapped_column()]
            last_name: Annotated[str, mapped_column()]

            # Using Annotated syntax (descriptor extracted automatically)
            full_name: Annotated[str, hybrid_property(_full_name)] = readonly_field(str)

            # Using explicit SQLAlchemyField
            full_name = readonly_field(
                str,
                SQLAlchemyField(attr=hybrid_property(_full_name)),
            )
        ```

    Note:
        Accessing a readonly_field on an entity not loaded via from_sa_model()
        raises RuntimeError. For Pydantic models, add readonly_field to
        model_config's ignored_types or inherit from SQLCrucibleBaseModel.
    """

    return cast(_T, ReadonlyFieldDescriptor(tp, sa_field))
