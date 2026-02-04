"""Unified converter for dict-like types.

This module handles conversion between all dict-like types:
- dict -> dict
- dict -> TypedDict
- TypedDict -> dict
- TypedDict -> TypedDict

Uses registry-based value conversion. Keys are assumed compatible - no key
conversion is performed. If key types are incompatible, the factory returns None.
"""

import builtins
from dataclasses import dataclass
from typing import (
    Any,
    Required,
    NotRequired,
    get_origin,
    get_args,
    get_type_hints,
    Self,
)
from typing_extensions import is_typeddict, NoExtraItems

from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry
from sqlcrucible.utils.types.annotations import TypeAnnotation, unwrap


@dataclass(slots=True, frozen=True)
class DictInfo:
    """Information about a dict-like type (dict or TypedDict).

    Attributes:
        tp: The original type.
        key_type: The key type (str for TypedDict, extracted K for dict[K,V], Any for dict).
        fields: Mapping of field names to their type annotations.
        extra_items: Type annotation for extra items, or None if closed.
    """

    tp: type
    key_type: Any  # type or Any
    fields: dict[str, TypeAnnotation]
    extra_items: TypeAnnotation | None

    @classmethod
    def create(cls, tp: type) -> Self:
        """Create a DictInfo from a dict-like type."""
        if is_typeddict(tp):
            return cls._from_typeddict(tp)
        else:
            return cls._from_dict(tp)

    @classmethod
    def _from_typeddict(cls, tp: type) -> Self:
        fields = {
            name: TypeAnnotation.create(annotation)
            for name, annotation in get_type_hints(tp, include_extras=True).items()
        }

        if bool(getattr(tp, "__closed__", False)):
            extra_items = None
        else:
            extra_items_tp = getattr(tp, "__extra_items__", NoExtraItems)
            extra_items = TypeAnnotation.create(
                extra_items_tp if extra_items_tp is not NoExtraItems else Any
            )

        return cls(tp=tp, key_type=str, fields=fields, extra_items=extra_items)

    @classmethod
    def _from_dict(cls, tp: type) -> Self:
        args = get_args(tp)
        key_tp, val_tp = args if args else (Any, Any)
        return cls(
            tp=tp,
            key_type=key_tp,
            fields={},
            extra_items=TypeAnnotation.create(val_tp),
        )

    def get_tp(self, key: str) -> TypeAnnotation | None:
        """Get the type annotation for a given key."""
        if key in self.fields:
            return self.fields[key]
        return self.extra_items

    def get_required(self, key: str) -> bool:
        """Check if a key is required in this dict type."""
        if key in self.fields:
            annotation = self.fields[key]

            required_qualifier = next(
                (it for it in annotation.qualifiers if it in (Required, NotRequired)), None
            )
            return (
                True
                if required_qualifier is Required
                else False
                if required_qualifier is NotRequired
                else getattr(self.tp, "__total__", True)
            )
        elif self.extra_items is not None:
            return False

        raise TypeError(
            f"Attempting to find whether key {key} is required in type {self.tp} which cannot contain key {key}"
        )


class DictConverter(Converter[dict, dict]):
    """Converter that transforms dict values using field-specific converters.

    Attributes:
        _target_info: DictInfo for the target type.
        _field_converters: Mapping of field names to their value converters.
        _extra_converter: Converter for extra items, or None if not allowed.
    """

    def __init__(
        self,
        target_info: DictInfo,
        field_converters: dict[str, Converter[Any, Any]],
        extra_converter: Converter[Any, Any] | None,
    ) -> None:
        self._target_info = target_info
        self._field_converters = field_converters
        self._extra_converter = extra_converter

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return True

    def convert(self, source: dict) -> dict:
        result: dict[Any, Any] = {}

        for key, value in source.items():
            if key in self._field_converters:
                result[key] = self._field_converters[key].convert(value)
            elif self._extra_converter:
                result[key] = self._extra_converter.convert(value)
            # else: drop key (target doesn't accept it)

        # Check required fields
        for key in self._field_converters:
            if key not in result and self._target_info.get_required(key):
                raise TypeError(f"Missing required key '{key}' for {self._target_info.tp}")

        return result

    def safe_convert(self, source: dict) -> dict:
        result: dict[Any, Any] = {}

        for key, value in source.items():
            if key in self._field_converters:
                result[key] = self._field_converters[key].safe_convert(value)
            elif self._extra_converter:
                result[key] = self._extra_converter.safe_convert(value)
            # else: drop key (target doesn't accept it)

        # Check required fields
        for key in self._field_converters:
            if key not in result and self._target_info.get_required(key):
                raise TypeError(f"Missing required key '{key}' for {self._target_info.tp}")

        return result


class DictConverterFactory(ConverterFactory[dict, dict]):
    """Factory that creates converters for dict-like type transformations.

    This factory matches when both source and target are dict-like types
    (dict or TypedDict). It resolves converters for value types using the
    registry, allowing nested type conversions.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        source_stripped = unwrap(source_tp)
        target_stripped = unwrap(target_tp)

        source_origin = getattr(source_stripped, "__origin__", source_stripped)
        target_origin = getattr(target_stripped, "__origin__", target_stripped)

        # Source is dict-like if it's Any or a dict subclass
        source_is_dict = source_stripped is Any or (
            isinstance(source_origin, type) and issubclass(source_origin, dict)
        )
        target_is_dict = isinstance(target_origin, type) and issubclass(target_origin, dict)

        return source_is_dict and target_is_dict

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        source_stripped = unwrap(source_tp)
        target_stripped = unwrap(target_tp)

        # Handle Any source type as unparameterized dict
        if source_stripped is Any:
            source_stripped = dict

        source_info = DictInfo.create(source_stripped)
        target_info = DictInfo.create(target_stripped)

        # Verify key types are compatible (NoOp converter exists)
        key_converter = registry.resolve(source_info.key_type, target_info.key_type)
        if key_converter is None:
            return None

        field_converters: dict[str, Converter[Any, Any]] = {}

        # Collect all field names from both source and target
        all_keys = set(source_info.fields.keys()) | set(target_info.fields.keys())

        for key in all_keys:
            source_val_tp = source_info.get_tp(key)
            target_val_tp = target_info.get_tp(key)

            if target_val_tp is None:
                # Target doesn't accept this key (closed TypedDict without this field)
                # Skip - will be dropped during conversion
                continue

            if source_val_tp is None:
                # Source has no type for this key but target requires it
                if target_info.get_required(key):
                    return None
                # Optional in target, skip
                continue

            # Resolve value converter
            value_converter = registry.resolve(source_val_tp.tp, target_val_tp.tp)
            if value_converter is None:
                return None

            field_converters[key] = value_converter

        # Handle extra items converter if both have extra_items
        extra_converter: Converter[Any, Any] | None = None
        if source_info.extra_items is not None and target_info.extra_items is not None:
            extra_converter = registry.resolve(
                source_info.extra_items.tp, target_info.extra_items.tp
            )
            if extra_converter is None:
                return None

        return DictConverter(target_info, field_converters, extra_converter)
