"""Converter for dictionary/mapping types.

This module handles conversion between dict types, recursively converting
both keys and values using the converter registry. It supports parameterized
dict types like dict[str, int] and preserves the target dict type.

Example:
    Converting dict[str, str] to dict[str, int] would convert each value
    from string to integer while preserving the keys.
"""

from sqlcrucible.conversion.registry import (
    Converter,
    ConverterFactory,
    ConverterRegistry,
)

from typing import Any, get_origin

from sqlcrucible.utils.types.params import get_type_params_for_base


class MappingConverterFactory(ConverterFactory[dict, dict]):
    """Factory that creates converters for dict-to-dict transformations.

    This factory matches when both source and target are dict types. It
    resolves converters for the key and value types separately, allowing
    nested type conversions.
    """

    class MappingConverter(Converter[dict, dict]):
        """Converter that transforms dict contents by converting keys and values.

        Attributes:
            _target: The target dict type to construct.
            _key_converter: Converter for transforming keys.
            _value_converter: Converter for transforming values.
        """

        def __init__(
            self,
            target: type[dict],
            key_converter: Converter[Any, Any],
            value_converter: Converter[Any, Any],
        ) -> None:
            self._target = target
            self._key_converter = key_converter
            self._value_converter = value_converter

        def matches(self, source_tp: Any, target_tp: Any) -> bool:
            return True

        def convert(self, source: dict) -> dict:
            return self._target(
                (self._key_converter.convert(k), self._value_converter.convert(v))
                for k, v in source.items()
            )

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        source_origin = get_origin(source_tp) or source_tp
        target_origin = get_origin(target_tp) or target_tp

        return (
            isinstance(source_origin, type)
            and issubclass(source_origin, dict)
            and target_origin is dict
        )

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        target_origin = get_origin(target_tp) or target_tp

        source_key, source_val = get_type_params_for_base(source_tp, dict)
        target_key, target_val = get_type_params_for_base(target_tp, dict)

        key_converter = registry.resolve(source_key, target_key)
        value_converter = registry.resolve(source_val, target_val)

        return (
            self.MappingConverter(target_origin, key_converter, value_converter)
            if key_converter and value_converter
            else None
        )
