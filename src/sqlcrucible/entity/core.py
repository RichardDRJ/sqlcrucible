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
    Iterator,
    Literal,
    Self,
    TypeVar,
    cast,
)

from sqlalchemy import MetaData, Table
from sqlalchemy.orm import DeclarativeBase
from typing_extensions import Format, TypedDict, get_annotations

from sqlcrucible.conversion import default_registry
from sqlcrucible.conversion.context import ConversionContext
from sqlcrucible.conversion.registry import Converter, ConverterRegistry
from sqlcrucible.entity.sa_conversion import (
    FromSAModelConverterFactory,
    ToSAModelConverterFactory,
)

from sqlcrucible.entity.column_projection import (
    ColumnProjection,
    RelationshipProjection,
    classify_field_converters,
)
from sqlcrucible.entity.field_resolution import (
    FieldConverter,
    entity_field_type,
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
    __own_sqlcrucible_fields__: ClassVar[dict[str, SQLCrucibleField] | None] = None
    __sa_model__: SQLAlchemyModel | None = None
    __identity_map__: IdentityMap | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Forward ``**kwargs`` so ``__init_subclass__`` cooperators further up
        # the MRO still run — most importantly ``typing.Generic.__init_subclass__``,
        # which populates ``__parameters__``. Without the super() call, a class
        # that inherits from both ``SQLCrucibleEntity`` and ``Generic[T]`` looks
        # un-parameterised to Pydantic, which then refuses to subscript it
        # ("does not inherit from typing.Generic").
        super().__init_subclass__(**kwargs)
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
        registered = cls.__dict__.get("__own_sqlcrucible_fields__") or {}
        for key, ann in get_annotations(cls, format=Format.FORWARDREF).items():
            if key in registered:
                continue
            canonical = canonicalise_typeform(cls, ann)
            cls.__register_sqlcrucible_field__(key, canonical, ConversionStrategy.EAGER)

    @classmethod
    @cache
    def __sqlcrucible_fields__(cls) -> dict[str, SQLCrucibleField]:
        """Every registered field for this class — those declared on it plus
        those inherited from base entities, bases first so iteration order is
        stable. A field re-declared on a subclass shadows the inherited one.

        The decls carry the *declared* field types (a ``TypeVar`` stays a
        ``TypeVar``); use :func:`entity_field_type` for the type resolved in a
        concrete subclass's context."""
        return {
            **{
                name: decl
                for base in cls.__bases__[::-1]
                if issubclass(base, SQLCrucibleEntity)
                for name, decl in base.__sqlcrucible_fields__().items()
            },
            **(cls.__dict__.get("__own_sqlcrucible_fields__") or {}),
        }

    @classmethod
    def __field_converters__(
        cls,
        resolve_converter: Callable[[type[SQLCrucibleEntity], SQLCrucibleField], Converter],
    ) -> list[FieldConverter]:
        """Build the field converters for one conversion direction over every
        eager field that isn't excluded from the SA model. Iterating
        :meth:`__sqlcrucible_fields__` means inherited fields are included
        automatically. The converter is resolved against the field's declaring
        class (where its ``Mapped[...]`` annotation lives), while ``target_type``
        is resolved against ``cls`` — so a converter inherited onto a concrete
        generic specialisation sees the specialised entity-side field type
        rather than the ``TypeVar`` it was declared with."""
        return [
            FieldConverter(
                source_name=decl.source_name,
                mapped_name=decl.mapped_name,
                converter=resolve_converter(decl.owner, decl),
                target_type=entity_field_type(cls, decl.source_name),
            )
            for decl in cls.__sqlcrucible_fields__().values()
            if decl.conversion_strategy is ConversionStrategy.EAGER and not decl.excluded
        ]

    @classmethod
    @cache
    def __to_sa_model_converters__(cls) -> list[FieldConverter]:
        return cls.__field_converters__(get_to_sa_model_converter)

    @classmethod
    @cache
    def __from_sa_model_converters__(cls) -> list[FieldConverter]:
        return cls.__field_converters__(get_from_sa_model_converter)

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
                conversion_spec.source_name: conversion_spec.converter.convert(
                    getattr(sa_model, conversion_spec.mapped_name),
                    ConversionContext(target_type=conversion_spec.target_type),
                )
                for conversion_spec in cls.__from_sa_model_converters__()
            }

            result = cls(**kwargs)
            result.__sa_model__ = sa_model
            result.__identity_map__ = identity_map
            identity_map[id(sa_model)] = result
            return result

    @classmethod
    @cache
    def __classified_field_converters__(
        cls,
    ) -> tuple[list[ColumnProjection], list[RelationshipProjection]]:
        """Cached partition of the to-SA converters into column projections
        (for column-level outputs) and relationship projections (for the
        nested-entity attributes the SA constructor accepts directly).

        Built via :func:`classify_field_converters`, which consults the
        SA mapper to dispatch each converter spec on the kind of property
        its mapped name resolves to.
        """
        return classify_field_converters(cls)

    @classmethod
    def __column_projections__(cls) -> list[ColumnProjection]:
        """Per-Pydantic-field projections onto SA columns. Plain fields
        project to a single column; composite-backed fields decompose
        into the underlying columns via SA's ``__composite_values__``
        protocol. Excludes relationship-mapped fields."""
        return cls.__classified_field_converters__()[0]

    @classmethod
    def __relationship_projections__(cls) -> list[RelationshipProjection]:
        """Per-Pydantic-field projections onto SA relationship attributes.
        Held aside from column projections so :meth:`to_column_dict`
        consumers can ignore them when building bulk-INSERT payloads."""
        return cls.__classified_field_converters__()[1]

    def to_columns(self) -> Iterator[tuple[str, Any]]:
        """Yield ``(column_name, value)`` pairs for every column-bound field
        on this entity.

        Plain fields yield a single pair; composite-backed fields yield
        one pair per underlying column via SA's standard
        ``__composite_values__`` protocol. Relationship-mapped fields
        are excluded.

        For joined-table inheritance the iteration spans every ancestor
        table; consumers targeting a single table can post-filter via
        ``Table.c``.
        """
        return (
            (column_name, column_value)
            for projection in self.__class__.__column_projections__()
            for column_name, column_value in zip(
                projection.column_names,
                projection.extractor(getattr(self, projection.source_name)),
                strict=True,
            )
        )

    def to_column_dict(self) -> dict[str, Any]:
        """Project this entity onto a flat ``{column_name: value}`` dict
        suitable for direct ``insert(table).values(...)``. Thin wrapper
        around :meth:`to_columns` for callers that need a dict."""
        return dict(self.to_columns())

    def to_sa_model(self) -> Any:
        """Convert this entity to a SQLAlchemy model instance.

        Creates a new SQLAlchemy model populated with data from this entity,
        applying any configured type converters for each field. Internally
        splices :meth:`to_columns` (column-shaped pairs, including
        decomposed composites) with the relationship-projection chain
        (nested-entity attributes), so the column-projection logic is a
        single source of truth shared with bulk-insert consumers.

        Returns:
            A SQLAlchemy model instance ready to be added to a session.
        """
        sa_type = self.__class__.__sqlalchemy_type__
        self.__sa_model__ = sa_type(
            **dict(self.to_columns()),
            **{
                projection.mapped_name: projection.converter.convert(
                    getattr(self, projection.source_name),
                    ConversionContext(target_type=projection.target_type),
                )
                for projection in self.__class__.__relationship_projections__()
            },
        )
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
        __init_subclass__ (EAGER) to populate this class's own field registry;
        :meth:`__sqlcrucible_fields__` flattens these across the MRO.
        """
        defs = cls.__dict__.get("__own_sqlcrucible_fields__")
        if defs is None:
            defs = {}
            cls.__own_sqlcrucible_fields__ = defs
        if source_name in defs:
            logger.debug(
                f"Multiple definitions of SQLCrucible field for {source_name} in class {cls}; will prefer the latest"
            )
        defs[source_name] = SQLCrucibleField(
            source_name=source_name,
            typeform=typeform,
            conversion_strategy=conversion_strategy,
            owner=cls,
        )


class SQLCrucibleBaseModel(BaseModel, SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__abstract__": True}
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
