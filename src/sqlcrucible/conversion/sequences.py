"""Converter for sequence types (list, set, frozenset).

This module handles conversion between sequence types, recursively converting
each element using the converter registry. It supports converting between
different sequence types (e.g., list to set) and parameterized types.

Supported sequence types:
    - list
    - set
    - frozenset

Example:
    Converting list[str] to set[int] would convert each string element to
    an integer and collect the results into a set.
"""

from typing import Any, Sequence, get_args, get_origin

from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry
from sqlcrucible.utils.types.params import get_type_params_for_base

#: Union of supported sequence types for conversion
KnownSequenceType = list | set | frozenset

#: Tuple of sequence type classes, extracted from KnownSequenceType for isinstance/issubclass checks
SEQUENCE_TYPES = get_args(KnownSequenceType)


def _get_element_type(tp: Any) -> Any:
    """Extract the element type from a parameterized sequence type.

    Args:
        tp: A sequence type annotation (e.g., list[int], set[str]).

    Returns:
        The element type if found, otherwise Any.
    """
    origin = get_origin(tp) or tp
    for seq_type in SEQUENCE_TYPES:
        if issubclass(origin, seq_type):
            params = get_type_params_for_base(tp, seq_type)
            return params[0] if params else Any
    return Any


class SequenceConverter(Converter[Sequence, KnownSequenceType]):
    """Converter that transforms sequence contents by converting each element.

    Attributes:
        _target: The target sequence type to construct (list, set, or frozenset).
        _inner: Converter for transforming individual elements.
    """

    def __init__(self, target: type[KnownSequenceType], inner: Converter[Any, Any]) -> None:
        self._target = target
        self._inner = inner

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return True

    def convert(self, source: Sequence) -> Any:
        return self._target(self._inner.convert(it) for it in source)

    def safe_convert(self, source: Sequence) -> Any:
        return self._target(self._inner.safe_convert(it) for it in source)


class SequenceConverterFactory(ConverterFactory[Sequence, KnownSequenceType]):
    """Factory that creates converters for sequence-to-sequence transformations.

    This factory matches when both source and target are known sequence types
    (list, set, frozenset). It resolves a converter for the element type,
    allowing nested type conversions.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        source_origin = get_origin(source_tp) or source_tp
        target_origin = get_origin(target_tp) or target_tp

        return (
            isinstance(source_origin, type)
            and issubclass(source_origin, SEQUENCE_TYPES)
            and any(target_origin is it for it in SEQUENCE_TYPES)
        )

    def converter(
        self,
        source_tp: Any,
        target_tp: Any,
        registry: ConverterRegistry,
    ) -> Converter[Any, Any] | None:
        target_origin = get_origin(target_tp) or target_tp

        target_elem = _get_element_type(target_tp)
        source_elem = _get_element_type(source_tp)

        inner_converter = registry.resolve(source_elem, target_elem)
        return (
            SequenceConverter(target_origin, inner_converter)
            if inner_converter is not None
            else None
        )
