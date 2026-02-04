"""Converter for Literal types.

This module handles conversion between Literal types. A converter is created
when the source Literal's values are a subset of the target Literal's values.
At runtime, it validates that the actual value is one of the target Literal's
allowed values.

Example:
    Converting Literal["a"] to Literal["a", "b"] succeeds because {"a"} ⊆ {"a", "b"}.
    Converting Literal["a", "c"] to Literal["a", "b"] fails because {"a", "c"} ⊄ {"a", "b"}.
"""

from typing import Any, Literal, get_args, get_origin

from sqlcrucible.conversion.exceptions import TypeMismatchError
from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry
from sqlcrucible.utils.types.equivalence import strip_wrappers


def _is_literal(tp: Any) -> bool:
    """Check if a type annotation represents a Literal type.

    Args:
        tp: A type annotation to check.

    Returns:
        True if the type is a Literal type (after stripping wrappers).
    """
    stripped = strip_wrappers(tp)
    return get_origin(stripped) is Literal


def _get_literal_values(tp: Any) -> frozenset[Any]:
    """Get the set of allowed values from a Literal type.

    Args:
        tp: A Literal type annotation.

    Returns:
        A frozenset of the allowed values.
    """
    stripped = strip_wrappers(tp)
    return frozenset(get_args(stripped))


class LiteralConverter(Converter[Any, Any]):
    """Converter that validates values against a target Literal type.

    Attributes:
        _target_tp: The full target Literal type annotation.
        _allowed_values: The set of values allowed by the target Literal.
    """

    def __init__(self, target_tp: Any) -> None:
        self._target_tp = target_tp
        self._allowed_values = _get_literal_values(target_tp)

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        if not (_is_literal(source_tp) and _is_literal(target_tp)):
            return False
        source_values = _get_literal_values(source_tp)
        target_values = _get_literal_values(target_tp)
        return source_values <= target_values

    def convert(self, source: Any) -> Any:
        return source

    def safe_convert(self, source: Any) -> Any:
        if source not in self._allowed_values:
            raise TypeMismatchError(
                source,
                self._target_tp,
                message=(
                    f"Value {source!r} is not a valid literal value. "
                    f"Expected one of: {sorted(self._allowed_values, key=repr)}"
                ),
            )
        return source


class LiteralConverterFactory(ConverterFactory[Any, Any]):
    """Factory that creates converters for Literal type transformations.

    This factory matches when both source and target are Literal types and
    the source Literal's values are a subset of the target Literal's values.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        if not (_is_literal(source_tp) and _is_literal(target_tp)):
            return False
        source_values = _get_literal_values(source_tp)
        target_values = _get_literal_values(target_tp)
        return source_values <= target_values

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        return LiteralConverter(strip_wrappers(target_tp))
