"""Converter for union types (Union[X, Y] and X | Y).

This module handles conversion between union types by trying converters
based on the runtime value's type. Converters are grouped by their source
origin type and selected using the value's MRO for efficient lookup.

The converter uses safe_convert() to validate values, only trying converters
whose source origin matches the runtime type's inheritance hierarchy.

Example:
    Converting list[int] | str | int to list[bool] | str:
    - For a list value: only tries list[int] -> list[bool]
    - For a str value: only tries str -> str
    - For an int value: only tries int -> str
    - For a bool value: finds int in MRO, tries int -> str
"""

from collections import defaultdict
from collections.abc import Sequence
from types import UnionType
from typing import Any, Union, get_args, get_origin

from sqlcrucible.conversion.exceptions import ConversionError, NoConverterFoundError
from sqlcrucible.conversion.noop import NoOpConverter
from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry
from sqlcrucible.utils.types.annotations import unwrap


def _is_union(tp: Any) -> bool:
    """Check if a type annotation represents a union type.

    Handles both direct unions (Union[X, Y], X | Y) and unions wrapped
    in other type forms like Annotated or Mapped.

    Args:
        tp: A type annotation to check.

    Returns:
        True if the type is a union or contains a union after stripping wrappers.
    """
    origin = get_origin(tp)
    if origin is Union or origin is UnionType:
        return True

    stripped = unwrap(tp)
    if stripped is not tp:
        stripped_origin = get_origin(stripped)
        return stripped_origin is Union or stripped_origin is UnionType

    return False


def _get_source_origin(source_tp: Any) -> type:
    """Get the origin type for grouping converters.

    Args:
        source_tp: A source type annotation.

    Returns:
        The origin type (e.g., list for list[int], str for str).
    """
    stripped = unwrap(source_tp)
    origin = get_origin(stripped)
    if origin is not None:
        return origin
    return stripped


class UnionConverter(Converter[Any, Any]):
    """Converter that handles union types using MRO-based lookup.

    Converters are grouped by their source origin type. At runtime, the
    value's type MRO is used to find applicable converters, avoiding
    unnecessary attempts with incompatible converters.

    Attributes:
        _target_tp: The target union type (for error messages).
        _converters_by_origin: Converters grouped by source origin type.
        _any_converters: Converters with Any as source (tried for all values).
    """

    def __init__(
        self,
        target_tp: Any,
        converters_by_origin: dict[type, list[Converter[Any, Any]]],
        any_converters: list[Converter[Any, Any]],
    ) -> None:
        self._target_tp = target_tp
        self._converters_by_origin = converters_by_origin
        self._any_converters = any_converters

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return _is_union(source_tp) or _is_union(target_tp)

    def convert(self, source: Any) -> Any:
        source_type = type(source)
        candidates: list[Converter[Any, Any]] = []

        # Find converters whose source origin is in the value's MRO
        for origin in source_type.__mro__:
            if origin in self._converters_by_origin:
                candidates.extend(self._converters_by_origin[origin])

        # Always include Any converters
        candidates.extend(self._any_converters)

        # Try candidates using safe_convert
        for converter in candidates:
            try:
                return converter.safe_convert(source)
            except ConversionError:
                continue

        raise NoConverterFoundError(source, self._target_tp)

    def safe_convert(self, source: Any) -> Any:
        # Union conversion always uses safe_convert internally
        return self.convert(source)


class UnionConverterFactory(ConverterFactory[Any, Any]):
    """Factory that creates converters for union type transformations.

    This factory matches when either source or target is a union type.
    It builds a converter for each member of the source union, finding
    the best match in the target union for each, then groups them by
    source origin for efficient runtime lookup.

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
            stripped_source = unwrap(source_tp)
            source_members = list(dict.fromkeys(get_args(stripped_source)))
        else:
            source_members = [source_tp]

        if _is_union(target_tp):
            stripped_target = unwrap(target_tp)
            target_members = list(dict.fromkeys(get_args(stripped_target)))
        else:
            target_members = [target_tp]

        # Fast path: source is subset of target, no conversion needed
        if set(source_members) <= set(target_members):
            return NoOpConverter(Any)

        # Build converters grouped by source origin
        converters_by_origin: dict[type, list[Converter[Any, Any]]] = defaultdict(list)
        any_converters: list[Converter[Any, Any]] = []

        for source_member in source_members:
            conv = self._best_converter(source_member, target_members, registry)
            if conv is None:
                return None

            origin = _get_source_origin(source_member)

            # Any/object origins go in any_converters (tried for all values)
            if origin is Any or origin is object:
                any_converters.append(conv)
            else:
                converters_by_origin[origin].append(conv)

        # Sort each origin group to prefer NoOpConverters
        for origin in converters_by_origin:
            converters_by_origin[origin].sort(
                key=lambda c: 0 if isinstance(c, NoOpConverter) else 1
            )
        any_converters.sort(key=lambda c: 0 if isinstance(c, NoOpConverter) else 1)

        return UnionConverter(target_tp, dict(converters_by_origin), any_converters)

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
