"""Field-level annotations for SQLAlchemy mapping configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import ORMDescriptor

from sqlcrucible.conversion.context import ConversionContext

__all__ = [
    "SQLAlchemyField",
    "ExcludeSAField",
    "ConvertFromSAWith",
    "ConvertToSAWith",
    "ConversionContext",
]


@dataclass(frozen=True, slots=True)
class SQLAlchemyField:
    """Configuration for mapping an entity field to SQLAlchemy.

    This annotation can be used to customize how entity fields are mapped to
    SQLAlchemy columns or relationships.

    Attributes:
        name: The name to use for the mapped attribute (defaults to field name)
        attr: An ORM descriptor to use directly (e.g., hybrid_property, association_proxy)
        tp: The type to use for the mapped attribute
    """

    name: str | None = None
    attr: ORMDescriptor[Any] | None = None
    tp: Any | None = None

    @classmethod
    def merge_all(cls, *fields: SQLAlchemyField | None) -> SQLAlchemyField:
        """Merge multiple SQLAlchemyField annotations, with later values taking precedence."""
        result = SQLAlchemyField()
        for field in fields:
            if field is None:
                continue
            result = SQLAlchemyField(
                name=field.name or result.name,
                attr=field.attr or result.attr,
                tp=field.tp or result.tp,
            )
        return result


@dataclass(frozen=True, slots=True)
class ExcludeSAField:
    value: bool = True


@dataclass(slots=True, frozen=True)
class ConvertFromSAWith:
    """Annotation specifying a custom converter from SQLAlchemy to entity.

    The callable receives ``(value, context)``. ``context.target_type`` is the
    resolved entity-side field type — for a concrete specialisation of a generic
    entity it's the specialised type on the subclass, not the ``TypeVar`` — so a
    converter can validate against it without having to guess.

    Example:
        ```python
        from typing import Annotated
        from pydantic import TypeAdapter


        class MyEntity(SQLCrucibleEntity):
            created_at: Annotated[
                datetime,
                mapped_column(),
                ConvertFromSAWith(lambda dt, ctx: dt.astimezone(timezone.utc)),
            ]
            payload: Annotated[
                SomeModel | None,
                mapped_column(JSON),
                ConvertFromSAWith(
                    lambda v, ctx: (
                        None if v is None else TypeAdapter(ctx.target_type).validate_python(v)
                    )
                ),
            ]
        ```
    """

    fn: Callable[[Any, ConversionContext], Any]


@dataclass(slots=True, frozen=True)
class ConvertToSAWith:
    """Annotation specifying a custom converter from entity to SQLAlchemy.

    The callable receives ``(value, context)``. ``context.target_type`` is the
    resolved entity-side field type of the value being converted.

    Example:
        ```python
        from typing import Annotated


        class MyEntity(SQLCrucibleEntity):
            created_at: Annotated[
                datetime,
                mapped_column(),
                ConvertToSAWith(lambda dt, ctx: dt.astimezone(timezone.utc)),
            ]
        ```
    """

    fn: Callable[[Any, ConversionContext], Any]
