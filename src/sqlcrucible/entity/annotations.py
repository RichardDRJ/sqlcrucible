"""Field-level annotations for SQLAlchemy mapping configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Mapped

from sqlcrucible.conversion.function import FunctionConverter
from sqlcrucible.conversion.registry import Converter


@dataclass(frozen=True, slots=True)
class SQLAlchemyField:
    """Configuration for mapping an entity field to SQLAlchemy.

    This annotation can be used to customize how entity fields are mapped to
    SQLAlchemy columns or relationships.

    Attributes:
        name: The name to use for the mapped attribute (defaults to field name)
        attr: A Mapped[] attribute to use directly
        tp: The type to use for the mapped attribute
    """

    name: str | None = None
    attr: Mapped[Any] | None = None
    tp: Any | None = None

    @classmethod
    def merge_all(cls, *fields: "SQLAlchemyField | None") -> "SQLAlchemyField":
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


@dataclass(slots=True)
class ConvertFromSAWith:
    """Annotation specifying custom converter from SQLAlchemy to entity.

    Use this annotation to provide a custom conversion function when loading
    values from SQLAlchemy models into entity instances.

    Example:
        ```python
        from typing import Annotated


        class MyEntity(SQLCrucibleEntity):
            created_at: Annotated[
                datetime, mapped_column(), ConvertFromSAWith(lambda dt: dt.astimezone(timezone.utc))
            ]
        ```
    """

    fn: Callable[[Any], Any]

    @property
    def converter(self) -> Converter:
        """Get the Converter instance for this function."""
        return FunctionConverter(self.fn)


@dataclass(slots=True)
class ConvertToSAWith:
    """Annotation specifying custom converter from entity to SQLAlchemy.

    Use this annotation to provide a custom conversion function when saving
    entity values into SQLAlchemy models.

    Example:
        ```python
        from typing import Annotated


        class MyEntity(SQLCrucibleEntity):
            created_at: Annotated[
                datetime, mapped_column(), ConvertToSAWith(lambda dt: dt.astimezone(timezone.utc))
            ]
        ```
    """

    fn: Callable[[Any], Any]

    @property
    def converter(self) -> Converter:
        """Get the Converter instance for this function."""
        return FunctionConverter(self.fn)
