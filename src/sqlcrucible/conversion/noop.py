"""No-operation converter for compatible types.

This module provides converters that pass values through unchanged when the
source and target types are equivalent. This is the most common converter,
used when no transformation is needed (e.g., str -> str, int -> int).

The NoOpConverter still performs runtime type validation to catch mismatches
early rather than allowing invalid values to propagate through the system.
"""

from sqlcrucible.utils.types.equivalence import (
    types_are_non_parameterised_and_equal,
    strip_wrappers,
)
from typing import Any, get_origin


from sqlcrucible.conversion.exceptions import TypeMismatchError
from sqlcrucible.conversion.registry import Converter, ConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry


class NoOpConverter(Converter[Any, Any]):
    """Converter that passes values through unchanged with type validation.

    This converter is used when source and target types are equivalent and
    no transformation is needed. It validates at runtime that the value
    is actually an instance of the expected type.

    Attributes:
        _target_tp: The full target type annotation.
        _target_origin: The origin type for isinstance checks (e.g., list for list[int]).
    """

    def __init__(self, target_tp: Any):
        self._target_tp = target_tp
        self._target_origin = get_origin(target_tp) or target_tp

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return types_are_non_parameterised_and_equal(source_tp, target_tp)

    def convert(self, source: Any) -> Any:
        if not (self._target_origin is Any or isinstance(source, self._target_origin)):
            raise TypeMismatchError(source, self._target_tp)
        return source


class NoOpConverterFactory(ConverterFactory[Any, Any]):
    """Factory that creates NoOpConverters for equivalent type pairs.

    This factory matches when the source and target types are structurally
    equivalent (ignoring wrapper types like Annotated or Mapped). It's
    typically registered first in the converter registry as a fast path
    for the common case where no conversion is needed.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return types_are_non_parameterised_and_equal(source_tp, target_tp)

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        return NoOpConverter(strip_wrappers(target_tp))
