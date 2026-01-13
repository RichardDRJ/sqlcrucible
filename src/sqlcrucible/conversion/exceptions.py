"""Exceptions for the type conversion system.

This module defines exceptions raised during type conversion operations.
Using specific exception types allows callers to handle conversion failures
differently from other errors, and provides better error messages.
"""

from typing import Any


class ConversionError(Exception):
    """Base exception for type conversion failures.

    This exception is raised when a value cannot be converted from one type
    to another. It provides context about the source value, source type,
    and target type to help diagnose the issue.

    Attributes:
        source: The value that failed to convert.
        source_type: The type of the source value.
        target_type: The type we attempted to convert to.
        message: Human-readable description of the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        source: Any = None,
        source_type: type | None = None,
        target_type: Any = None,
    ) -> None:
        self.source = source
        self.source_type = source_type or (type(source) if source is not None else None)
        self.target_type = target_type
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class TypeMismatchError(ConversionError):
    """Raised when a value's type doesn't match the expected type.

    This is raised by NoOpConverter when runtime type validation fails,
    indicating that the actual value type differs from what was declared.
    """

    def __init__(
        self,
        source: Any,
        target_type: Any,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                f"Type mismatch: expected {target_type}, "
                f"got {type(source).__name__} (value: {source!r})"
            )
        super().__init__(
            message,
            source=source,
            target_type=target_type,
        )


class NoConverterFoundError(ConversionError):
    """Raised when no converter can handle a type conversion.

    This is raised by UnionConverter when none of the available converters
    can successfully convert the source value to any of the target union members.
    """

    def __init__(
        self,
        source: Any,
        target_type: Any,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"No converter found: cannot convert {type(source).__name__} to {target_type}"
        super().__init__(
            message,
            source=source,
            target_type=target_type,
        )
