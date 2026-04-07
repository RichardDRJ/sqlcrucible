from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from sqlcrucible._types.match import mro_distance

from functools import cache
from logging import getLogger
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    Literal,
    Self,
    TypeVar,
    cast,
)

from sqlalchemy import MetaData, Table
from sqlalchemy.orm import DeclarativeBase
from typing_extensions import Format, TypedDict, get_annotations

from sqlcrucible.conversion import default_registry
from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.entity.sa_conversion import (
    FromSAModelConverterFactory,
    ToSAModelConverterFactory,
)

from sqlcrucible.entity.field_resolution import (
    FieldConverter,
    get_from_sa_model_converter,
    get_to_sa_model_converter,
)
from sqlcrucible.conversion.caching import IdentityMap, _identity_map, CachingConverterFactory
from sqlcrucible.entity.field_definitions import (
    CanonicalisedTypeform,
    SQLCrucibleField,
    ConversionStrategy,
    canonicalise_typeform,
)
from sqlcrucible.entity.descriptors import ReadonlyFieldDescriptor


# --- Lazy property descriptors ---

_LP_T = TypeVar("_LP_T")
_LP_R = TypeVar("_LP_R")

UNSET = cast(Any, object())


class _lazyproperty(Generic[_LP_T, _LP_R]):
    """Descriptor that lazily computes a value once and caches it.

    Used for class-level properties that are expensive to compute and
    should only be computed once.
    """

    def __init__(self, func: Callable[[type[_LP_T]], _LP_R]) -> None:
        self._func = func
        self._value: _LP_R = UNSET

    def __get__(self, instance: Any, owner: type[_LP_T]) -> _LP_R:
        if self._value is UNSET:
            self._value = self._func(owner)
        return self._value


def lazyproperty(func: Callable[[type[_LP_T]], _LP_R]) -> _LP_R:
    return cast(_LP_R, _lazyproperty(func))


#: Direction of conversion: entity to SQLAlchemy model or vice versa
ConversionDirection = Literal["to_sa", "from_sa"]

# Entity-specific registry that includes SA model converters.
# This extends the base default_registry with entity conversion capabilities.
_entity_registry = ConverterRegistry(
    *default_registry,
    CachingConverterFactory(FromSAModelConverterFactory()),
    CachingConverterFactory(ToSAModelConverterFactory()),
)

logger = getLogger(__name__)


class SQLAlchemyBase(DeclarativeBase):
    """Default SQLAlchemy declarative base for auto-generated models.

    This is used as the base class for SQLAlchemy models when no custom
    base is specified.
    """

    pass


class SQLAlchemyParameters(TypedDict, extra_items=Any, total=False):
    """Type definition for SQLAlchemy configuration parameters.

    These can be set on entity classes to configure the generated
    SQLAlchemy model.

    Example:
        class MyEntity(SQLCrucibleEntity):
            __sqlalchemy_params__ = {
                "__tablename__": "my_table",
                "__table_args__": {"schema": "custom_schema"},
            }
    """

    __tablename__: str
    """The database table name."""

    __table__: Table
    """Explicit table definition."""

    __abstract__: bool
    """Whether this is an abstract base class."""

    __mapper_args__: dict[str, Any]
    """Additional arguments for the SQLAlchemy mapper."""

    metadata: MetaData
    """The SQLAlchemy MetaData instance to use for this class and its children."""


SQLAlchemyModel = Any
SQLAlchemyModelType = type[SQLAlchemyModel]


def _construct_automodel(cls: type[SQLCrucibleEntity]):
    import sqlcrucible.entity.automodel

    return sqlcrucible.entity.automodel.auto_sqlalchemy_model_factory(cls)


def _get_automodel(cls: type[SQLCrucibleEntity]):
    return cls.__sqlalchemy_automodel__


class SQLCrucibleEntity:
    """Base class for entities that auto-generate SQLAlchemy models.

    Subclasses define their schema using type annotations with SQLAlchemy
    markers (mapped_column, relationship, etc.). The SQLAlchemy model is
    automatically generated and accessible via __sqlalchemy_type__.

    Class Attributes:
        __sqlalchemy_base__: Optional custom DeclarativeBase for the SA model.
        __sqlalchemy_params__: SQLAlchemy configuration (tablename, etc.).
        __converter_registry__: Converter registry for field type conversion.
        __sqlalchemy_automodel__: The auto-generated SQLAlchemy model class.
        __sqlalchemy_type__: The SQLAlchemy model class to use (defaults to __sqlalchemy_automodel__).

    Example:
        ```python
        @dataclass
        class User(SQLCrucibleEntity):
            __sqlalchemy_params__ = {"__tablename__": "users"}

            id: Annotated[int, mapped_column(Integer, primary_key=True)]
            name: Annotated[str, mapped_column(String(50))]
            email: Annotated[str | None, mapped_column(String(100))]


        # Use the entity
        user = User(id=1, name="Alice", email="alice@example.com")
        sa_model = user.to_sa_model()  # Convert to SQLAlchemy

        # Convert back
        user2 = User.from_sa_model(sa_model)
        ```
    """

    __sqlalchemy_base__: ClassVar[SQLAlchemyModelType]
    __sqlalchemy_params__: ClassVar[SQLAlchemyParameters] = {}
    __converter_registry__: ClassVar[ConverterRegistry] = _entity_registry

    __sqlalchemy_automodel__: ClassVar[SQLAlchemyModelType]
    __sqlalchemy_type__: ClassVar[SQLAlchemyModelType] = SQLAlchemyBase
    __sqlcrucible_fields__: ClassVar[dict[str, SQLCrucibleField] | None] = None
    __sa_model__: SQLAlchemyModel | None = None
    __identity_map__: IdentityMap | None = None

    def __init_subclass__(cls) -> None:
        if "__sqlalchemy_automodel__" not in cls.__dict__:
            cls.__sqlalchemy_automodel__ = lazyproperty(_construct_automodel)

        # __sqlalchemy_type__ defaults to __sqlalchemy_automodel__ unless overridden
        if "__sqlalchemy_type__" not in cls.__dict__:
            cls.__sqlalchemy_type__ = lazyproperty(_get_automodel)

        # Register annotation-based fields as EAGER, skipping those already
        # registered (e.g. by ReadonlyFieldDescriptor.__set_name__).
        # get_annotations with FORWARDREF handles both stringified annotations
        # (from __future__ import annotations) and Python 3.14+ lazy annotations
        # (PEP 749), returning ForwardRef for unresolvable names. canonicalise_typeform
        # wraps these in LazyCanonicalisedTypeform for deferred resolution.
        registered = cls.__dict__.get("__sqlcrucible_fields__") or {}
        for key, ann in get_annotations(cls, format=Format.FORWARDREF).items():
            if key in registered:
                continue
            canonical = canonicalise_typeform(cls, ann)
            cls.__register_sqlcrucible_field__(key, canonical, ConversionStrategy.EAGER)

    @classmethod
    @cache
    def __to_sa_model_converters__(cls) -> list[FieldConverter]:
        own_fields: dict[str, SQLCrucibleField] = cls.__dict__.get("__sqlcrucible_fields__") or {}
        return [
            *[
                converter
                for base in cls.__bases__[::-1]
                if issubclass(base, SQLCrucibleEntity)
                for converter in base.__to_sa_model_converters__()
            ],
            *[
                FieldConverter(
                    source_name=decl.source_name,
                    mapped_name=decl.mapped_name,
                    converter=get_to_sa_model_converter(cls, decl),
                )
                for decl in own_fields.values()
                if decl.conversion_strategy is ConversionStrategy.EAGER and not decl.excluded
            ],
        ]

    @classmethod
    @cache
    def __from_sa_model_converters__(cls) -> list[FieldConverter]:
        own_fields: dict[str, SQLCrucibleField] = cls.__dict__.get("__sqlcrucible_fields__") or {}
        return [
            *[
                converter
                for base in cls.__bases__[::-1]
                if issubclass(base, SQLCrucibleEntity)
                for converter in base.__from_sa_model_converters__()
            ],
            *[
                FieldConverter(
                    source_name=decl.source_name,
                    mapped_name=decl.mapped_name,
                    converter=get_from_sa_model_converter(cls, decl),
                )
                for decl in own_fields.values()
                if decl.conversion_strategy is ConversionStrategy.EAGER and not decl.excluded
            ],
        ]

    @classmethod
    def from_sa_model(cls, sa_model: Any) -> Self:
        """Create an entity instance from a SQLAlchemy model.

        This method converts a SQLAlchemy model instance into the corresponding
        entity class. For polymorphic models, it automatically selects the most
        specific entity subclass that matches the model type.

        Args:
            sa_model: A SQLAlchemy model instance to convert.

        Returns:
            An entity instance populated with data from the SQLAlchemy model.

        Raises:
            TypeError: If sa_model is None.
            ValueError: If sa_model is not compatible with this entity's SQLAlchemy type.
        """
        if sa_model is None:
            raise TypeError(
                f"Cannot create {cls.__name__} from None. "
                f"Expected an instance of {cls.__sqlalchemy_type__.__name__}."
            )
        if not isinstance(sa_model, cls.__sqlalchemy_type__):
            raise ValueError(
                f"Cannot create {cls.__name__} from {type(sa_model).__name__}: "
                f"expected an instance of {cls.__sqlalchemy_type__.__name__} or a subclass.\n"
                f"Hint: Make sure you're passing a SQLAlchemy model that was created from "
                f"this entity class or one of its subclasses."
            )
        best_subclasses = sorted(
            cls.__subclasses__(),
            key=lambda it: mro_distance(sa_model.__class__, it.__sqlalchemy_type__),
        )
        if best_subclasses:
            best_match = best_subclasses[0]
        else:
            best_match = cls

        return best_match._from_sa_model(sa_model)

    @classmethod
    def _from_sa_model(cls, sa_model: Any) -> Self:
        with _identity_map() as identity_map:
            kwargs = {
                conversion_spec.source_name: conversion_spec.converter.convert(value)
                for conversion_spec in cls.__from_sa_model_converters__()
                for value in (getattr(sa_model, conversion_spec.mapped_name),)
            }

            result = cls(**kwargs)
            result.__sa_model__ = sa_model
            result.__identity_map__ = identity_map
            identity_map[id(sa_model)] = result
            return result

    def to_sa_model(self) -> Any:
        """Convert this entity to a SQLAlchemy model instance.

        Creates a new SQLAlchemy model populated with data from this entity,
        applying any configured type converters for each field.

        Returns:
            A SQLAlchemy model instance ready to be added to a session.
        """
        kwargs = {
            conversion_spec.mapped_name: conversion_spec.converter.convert(value)
            for conversion_spec in self.__class__.__to_sa_model_converters__()
            for value in (getattr(self, conversion_spec.source_name),)
        }

        sa_type = self.__class__.__sqlalchemy_type__
        self.__sa_model__ = sa_type(**kwargs)
        return self.__sa_model__

    @classmethod
    def __register_sqlcrucible_field__(
        cls,
        source_name: str,
        typeform: CanonicalisedTypeform,
        conversion_strategy: ConversionStrategy = ConversionStrategy.EAGER,
    ) -> None:
        """Register a field's canonical type during class creation.

        Used by ReadonlyFieldDescriptor.__set_name__ (DEFERRED) and
        __init_subclass__ (EAGER) to build the master field registry.
        """
        defs = cls.__dict__.get("__sqlcrucible_fields__")
        if defs is None:
            defs = {}
            cls.__sqlcrucible_fields__ = defs
        if source_name in defs:
            logger.debug(
                f"Multiple definitions of SQLCrucible field for {source_name} in class {cls}; will prefer the latest"
            )
        defs[source_name] = SQLCrucibleField(
            source_name=source_name,
            typeform=typeform,
            conversion_strategy=conversion_strategy,
        )


class SQLCrucibleBaseModel(BaseModel, SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True}
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
