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

from sqlcrucible.conversion.caching import _identity_map
from sqlcrucible.entity.field_resolution import get_from_sa_model_converter
from sqlcrucible.conversion.registry import Converter
from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.field_definitions import SQLAlchemyFieldDefinition
from sqlcrucible._types.forward_refs import resolve_forward_refs
from typing_extensions import get_annotations, Format

if TYPE_CHECKING:
    from sqlcrucible.entity.core import SQLCrucibleEntity


_O = TypeVar("_O", bound="SQLCrucibleEntity")
_T = TypeVar("_T")


class ReadonlyFieldDescriptor(property, Generic[_T, _O]):
    """Descriptor implementation for readonly_field.

    See readonly_field() function for documentation.

    Subclasses property so that Pydantic's computed_field can extract the
    return type via fget.__annotations__['return'], enabling the shorthand:

        artist = computed_field(readonly_field(Artist, ...))
    """

    def __init__(
        self,
        tp: Any,
        descriptor: ORMDescriptor[Any] | None = None,
        sa_field: SQLAlchemyField | None = None,
    ):
        """Initialize a readonly field descriptor.

        Args:
            tp: The type of the field value (can be a type, string forward ref, or parameterized type)
            descriptor: Optional ORM descriptor (e.g., hybrid_property, association_proxy)
            sa_field: Optional SQLAlchemyField configuration for the mapped attribute
        """

        def fget(instance: Any) -> Any: ...

        fget.__annotations__["return"] = tp
        super().__init__(fget=fget)

        self._tp = tp
        self._descriptor = descriptor
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

        # Build SQLAlchemyField from provided arguments or extract from annotation
        sa_field = self._sa_field
        if self._descriptor is not None:
            # Merge descriptor into sa_field (or create new one if sa_field is None)
            sa_field = SQLAlchemyField.merge_all(
                sa_field,
                SQLAlchemyField(attr=self._descriptor),
            )
        elif sa_field is None:
            # Try to extract from annotation
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
    def __get__(self, instance: None, owner: type, /) -> Self: ...

    @overload
    def __get__(self, instance: _O, owner: type[_O], /) -> _T: ...

    @overload
    def __get__(self, instance: Any, owner: type | None = None, /) -> Any: ...

    def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
        """Get the field value from an entity instance.

        When accessed on the class, returns the descriptor itself.
        When accessed on an instance, loads the value from the SQLAlchemy model.
        Results are cached per instance so that repeated access returns the
        same object.

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

        cache = instance.__dict__.get("__readonly_cache__")
        if cache is not None and self._name in cache:
            return cache[self._name]

        field_info = self.sa_field_info
        resolved_owner = cast(
            type["SQLCrucibleEntity"], owner if owner is not None else type(instance)
        )
        if self._converter is None:
            self._converter = get_from_sa_model_converter(resolved_owner, field_info)

        model = instance.__sa_model__
        if model is None:
            raise RuntimeError(
                f"Cannot access readonly_field '{self._name}' on {type(instance).__name__}: "
                f"this entity was not loaded from a SQLAlchemy model.\n"
                f"Hint: readonly_field values are only available on entities created via "
                f"from_sa_model(). If you need this field on manually-created entities, "
                f"consider using a regular field instead."
            )

        with _identity_map(instance.__identity_map__):
            result = self._converter.convert(getattr(model, field_info.mapped_name))

        instance.__dict__.setdefault("__readonly_cache__", {})[self._name] = result
        return result


@overload
def readonly_field(tp: type[_T]) -> _T: ...


@overload
def readonly_field(tp: type[_T], arg1: SQLAlchemyField | ORMDescriptor[Any], /) -> _T: ...


@overload
def readonly_field(
    tp: type[_T],
    arg1: SQLAlchemyField | ORMDescriptor[Any],
    arg2: SQLAlchemyField | ORMDescriptor[Any],
    /,
) -> _T: ...


@overload
def readonly_field(tp: str) -> Any: ...


@overload
def readonly_field(tp: str, arg1: SQLAlchemyField | ORMDescriptor[Any], /) -> Any: ...


@overload
def readonly_field(
    tp: str,
    arg1: SQLAlchemyField | ORMDescriptor[Any],
    arg2: SQLAlchemyField | ORMDescriptor[Any],
    /,
) -> Any: ...


def readonly_field(tp: type[_T] | str, *args: SQLAlchemyField | ORMDescriptor[Any]) -> Any:
    """Create a readonly field descriptor.

    Readonly fields are loaded from the SQLAlchemy model but cannot be set
    on the entity. They are useful for computed properties like hybrid_property
    and association_proxy.

    Args:
        tp: The type of the field value
        *args: Optional SQLAlchemyField and/or ORMDescriptor (e.g., hybrid_property,
            association_proxy) in any order. If both are provided, the descriptor
            is merged into the SQLAlchemyField. If neither is provided, the descriptor
            is extracted from the field's Annotated type if present.

    Returns:
        A descriptor that loads the field value from the backing SQLAlchemy model.

    Example:
        ```python
        def _full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"


        class Person(SQLCrucibleBaseModel):
            first_name: Annotated[str, mapped_column()]
            last_name: Annotated[str, mapped_column()]

            # Simplest: pass descriptor directly
            full_name = readonly_field(str, hybrid_property(_full_name))

            # Alternative: use Annotated syntax (descriptor extracted automatically)
            full_name: Annotated[str, hybrid_property(_full_name)] = readonly_field(str)

            # With SQLAlchemyField (order doesn't matter)
            full_name = readonly_field(
                str,
                hybrid_property(_full_name),
                SQLAlchemyField(name="computed_full_name"),
            )

            # Or reversed order
            full_name = readonly_field(
                str,
                SQLAlchemyField(name="computed_full_name"),
                hybrid_property(_full_name),
            )
        ```

    Note:
        Accessing a readonly_field on an entity not loaded via from_sa_model()
        raises RuntimeError. For Pydantic models, add ReadonlyFieldDescriptor to
        model_config's ignored_types or inherit from SQLCrucibleBaseModel.
    """
    descriptor: ORMDescriptor[Any] | None = None
    sa_field: SQLAlchemyField | None = None

    for arg in args:
        if isinstance(arg, SQLAlchemyField):
            if sa_field is not None:
                raise TypeError("readonly_field() got multiple SQLAlchemyField arguments")
            sa_field = arg
        elif isinstance(arg, ORMDescriptor):
            if descriptor is not None:
                raise TypeError("readonly_field() got multiple ORMDescriptor arguments")
            descriptor = arg
        else:
            raise TypeError(
                f"readonly_field() arguments must be SQLAlchemyField or ORMDescriptor, "
                f"got {type(arg).__name__}"
            )

    return cast(_T, ReadonlyFieldDescriptor(tp, descriptor, sa_field))
