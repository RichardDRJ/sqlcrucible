from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from sqlcrucible._types.match import mro_distance

from functools import cache
from logging import getLogger
from typing import (
    Any,
    Callable,
    ClassVar,
    Final,
    Generic,
    Literal,
    Self,
    TypeVar,
    cast,
    get_origin,
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
from sqlcrucible.entity.field_definitions import SQLAlchemyFieldDefinition
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
    FromSAModelConverterFactory(),
    ToSAModelConverterFactory(),
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
    __sa_model__: SQLAlchemyModel | None = None

    def __init_subclass__(cls) -> None:
        if "__sqlalchemy_automodel__" not in cls.__dict__:
            cls.__sqlalchemy_automodel__ = lazyproperty(_construct_automodel)

        # __sqlalchemy_type__ defaults to __sqlalchemy_automodel__ unless overridden
        if "__sqlalchemy_type__" not in cls.__dict__:
            cls.__sqlalchemy_type__ = lazyproperty(_get_automodel)

        annotations = get_annotations(cls, eval_str=True, format=Format.VALUE)
        for key, ann in annotations.items():
            origin = get_origin(ann)
            if origin is ClassVar or origin is Final or ann is ClassVar or ann is Final:
                continue
            # Skip fields with readonly_field descriptor - they handle their own registration
            if isinstance(cls.__dict__.get(key), ReadonlyFieldDescriptor):
                continue
            if (field_definition := SQLAlchemyFieldDefinition.from_typeform(key, ann)) is not None:
                cls.__register_sqlalchemy_field_definition__(field_definition)

    @classmethod
    def __sqlalchemy_field_definitions__(cls) -> dict[str, SQLAlchemyFieldDefinition]:
        if "_sqlalchemy_field_definitions" not in cls.__dict__:
            cls._sqlalchemy_field_definitions = {}
        return cls._sqlalchemy_field_definitions

    @classmethod
    def __mapped_fields__(cls) -> list[SQLAlchemyFieldDefinition]:
        """Get field definitions for fields declared directly on this class.

        Returns only fields that are both in the class's own annotations
        (not inherited) and have SQLAlchemy field definitions registered.

        Returns:
            List of SQLAlchemyFieldDefinition for this class's own fields.
        """
        annotations = get_annotations(cls, eval_str=True, format=Format.VALUE)
        return [
            it
            for it in cls.__sqlalchemy_field_definitions__().values()
            if it.source_name in annotations
        ]

    @classmethod
    @cache
    def __to_sa_model_converters__(cls) -> list[FieldConverter]:
        return [
            *[
                converter
                for base in cls.__bases__[::-1]
                if issubclass(base, SQLCrucibleEntity)
                for converter in base.__to_sa_model_converters__()
            ],
            *[
                FieldConverter(
                    source_name=it.source_name,
                    mapped_name=it.mapped_name,
                    converter=get_to_sa_model_converter(cls, it),
                )
                for it in cls.__mapped_fields__()
                # Exclude readonly fields (defined via readonly_field descriptor)
                if not it.readonly
            ],
        ]

    @classmethod
    @cache
    def __from_sa_model_converters__(cls) -> list[FieldConverter]:
        return [
            *[
                converter
                for base in cls.__bases__[::-1]
                if issubclass(base, SQLCrucibleEntity)
                for converter in base.__from_sa_model_converters__()
            ],
            *[
                FieldConverter(
                    source_name=it.source_name,
                    mapped_name=it.mapped_name,
                    converter=get_from_sa_model_converter(cls, it),
                )
                for it in cls.__mapped_fields__()
                # Exclude readonly fields (defined via readonly_field descriptor)
                if not it.readonly
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
        kwargs = {}
        for conversion_spec in cls.__from_sa_model_converters__():
            value = getattr(sa_model, conversion_spec.mapped_name)
            kwargs[conversion_spec.source_name] = conversion_spec.converter.convert(value)

        result = cls(**kwargs)
        result.__sa_model__ = sa_model
        return result

    def to_sa_model(self) -> Any:
        """Convert this entity to a SQLAlchemy model instance.

        Creates a new SQLAlchemy model populated with data from this entity,
        applying any configured type converters for each field.

        Returns:
            A SQLAlchemy model instance ready to be added to a session.
        """
        kwargs = {}
        for conversion_spec in self.__class__.__to_sa_model_converters__():
            value = getattr(self, conversion_spec.source_name)
            kwargs[conversion_spec.mapped_name] = conversion_spec.converter.convert(value)

        sa_type = self.__class__.__sqlalchemy_type__
        self.__sa_model__ = sa_type(**kwargs)
        return self.__sa_model__

    @classmethod
    def __register_sqlalchemy_field_definition__(cls, field_def: SQLAlchemyFieldDefinition):
        source_name = field_def.source_name
        if source_name in cls.__sqlalchemy_field_definitions__():
            logger.debug(
                f"Multiple definition of SQLAlchemy field {source_name} in class {cls} and its bases; will prefer the latest"
            )
        cls.__sqlalchemy_field_definitions__()[source_name] = field_def


class SQLCrucibleBaseModel(BaseModel, SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True}
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
