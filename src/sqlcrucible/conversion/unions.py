"""Converter for union types (Union[X, Y] and X | Y).

This module handles conversion between union types by trying each possible
converter in order until one succeeds. It supports both typing.Union and
the Python 3.10+ pipe syntax (X | Y).

The converter tries converters in order of preference:
1. NoOpConverters (identity conversions) are tried first
2. Other converters are tried in the order their source types appear

Example:
    Converting str | int to int | float would try:
    - str -> int (if converter exists)
    - str -> float (if converter exists)
    - int -> int (NoOp, preferred)
    - int -> float (if converter exists)
"""

from sqlcrucible.utils.types.equivalence import strip_wrappers
from collections.abc import Sequence
from types import UnionType
from typing import Any, Union, get_args, get_origin, cast

from sqlcrucible.conversion.exceptions import ConversionError, NoConverterFoundError
from sqlcrucible.conversion.noop import NoOpConverter
from sqlcrucible.conversion.registry import Converter, ConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry


def _is_union(tp: Any) -> bool:
    """Check if a type annotation represents a union type.

    Handles both direct unions (Union[X, Y], X | Y) and unions wrapped
    in other type forms like Annotated or Mapped.

    Args:
        tp: A type annotation to check.

    Returns:
        True if the type is a union or contains a union after stripping wrappers.
    """
    # Check if the type itself is a union
    origin = get_origin(tp)
    if origin is Union or origin is UnionType:
        return True

    # Check if stripping wrappers reveals a union (e.g., Mapped[str | None])
    stripped = strip_wrappers(tp)
    if stripped is not tp:
        stripped_origin = get_origin(stripped)
        return stripped_origin is Union or stripped_origin is UnionType

    return False


class UnionConverter(Converter[Any, Any]):
    """Converter that handles union types by trying converters in sequence.

    Each converter in the list is tried in order. The first one that succeeds
    (doesn't raise ConversionError) wins. NoOpConverters are sorted to the front
    to prefer identity conversions when possible.

    Attributes:
        _target_tp: The target union type (for error messages).
        _converters: List of converters to try, in priority order.
    """

    def __init__(
        self,
        target_tp: Any,
        converters: list[Converter[Any, Any]],
    ) -> None:
        self._target_tp = target_tp
        self._converters = converters

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return _is_union(source_tp) or _is_union(target_tp)

    def convert(self, source: Any) -> Any:
        for converter in self._converters:
            try:
                return converter.convert(source)
            except ConversionError:
                continue

        raise NoConverterFoundError(source, self._target_tp)


class UnionConverterFactory(ConverterFactory[Any, Any]):
    """Factory that creates converters for union type transformations.

    This factory matches when either source or target is a union type.
    It builds a converter for each member of the source union, finding
    the best match in the target union for each.

    If the source union is a subset of the target union, a NoOpConverter
    is returned since no transformation is needed.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return _is_union(source_tp) or _is_union(target_tp)

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        # Get union members, stripping wrappers if necessary
        if _is_union(source_tp):
            stripped_source = strip_wrappers(source_tp)
            source_members = list(dict.fromkeys(get_args(stripped_source)))
        else:
            source_members = [source_tp]

        if _is_union(target_tp):
            stripped_target = strip_wrappers(target_tp)
            target_members = list(dict.fromkeys(get_args(stripped_target)))
        else:
            target_members = [target_tp]
        if set(source_members) <= set(target_members):
            return NoOpConverter(Any)

        converters = [self._best_converter(it, target_members, registry) for it in source_members]
        if any(it is None for it in converters):
            # If any source type can't be converter, we do not create a Union converter
            # return None since the source union cannot be mapped to the target union.
            return None

        converters = cast(
            list[Converter[Any, Any]],
            sorted(
                converters,
                key=lambda it: 0
                if isinstance(it, NoOpConverter)
                else 1,  # Prefer NoOpConverters where possible
            ),
        )
        return UnionConverter(target_tp, converters) if converters else None

    def _best_converter(
        self, source_tp: Any, target_tps: Sequence[Any], registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        converters = [
            converter
            for target_tp in target_tps
            if (converter := registry.resolve(source_tp, target_tp)) is not None
        ]
        if (
            noop_converter := next((it for it in converters if isinstance(it, NoOpConverter)), None)
        ) is not None:
            return noop_converter
        return next(iter(converters), None)
