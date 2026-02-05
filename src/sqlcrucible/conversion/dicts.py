"""Unified converter for dict-like types.

This module handles conversion between all dict-like types:
- dict -> dict
- dict -> TypedDict
- TypedDict -> dict
- TypedDict -> TypedDict

Uses registry-based value conversion. Keys are assumed compatible - no key
conversion is performed. If key types are incompatible, the factory returns None.
"""

from dataclasses import dataclass
from typing import (
    Any,
    Required,
    NotRequired,
    get_args,
    get_type_hints,
    Self,
)
from typing_extensions import is_typeddict, NoExtraItems

from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry
from sqlcrucible.utils.types.annotations import TypeAnnotation, unwrap


class _IncompatibleTypes(Exception):
    """Raised internally when types cannot be converted."""


@dataclass(slots=True, frozen=True)
class DictInfo:
    """Information about a dict-like type (dict or TypedDict).

    Attributes:
        tp: The original type.
        key_type: The key type (str for TypedDict, extracted K for dict[K,V], Any for dict).
        fields: Mapping of field names to their type annotations.
        extra_items: Type annotation for extra items, or None if closed.
        required_fields: Set of field names that are required.
    """

    tp: type
    key_type: Any  # type or Any
    fields: dict[str, TypeAnnotation]
    extra_items: TypeAnnotation | None
    required_fields: frozenset[str]

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

        total = getattr(tp, "__total__", True)
        required_fields = frozenset(
            name
            for name, annotation in fields.items()
            if cls._is_field_required(annotation, total=total)
        )

        return cls(
            tp=tp,
            key_type=str,
            fields=fields,
            extra_items=extra_items,
            required_fields=required_fields,
        )

    @staticmethod
    def _is_field_required(annotation: TypeAnnotation, *, total: bool) -> bool:
        """Determine if a field is required based on its annotation and total flag."""
        required_qualifier = next(
            (q for q in annotation.qualifiers if q in (Required, NotRequired)), None
        )
        if required_qualifier is Required:
            return True
        if required_qualifier is NotRequired:
            return False
        return total

    @classmethod
    def _from_dict(cls, tp: type) -> Self:
        args = get_args(tp)
        key_tp, val_tp = args if args else (Any, Any)
        return cls(
            tp=tp,
            key_type=key_tp,
            fields={},
            extra_items=TypeAnnotation.create(val_tp),
            required_fields=frozenset(),
        )

    def get_tp(self, key: str) -> TypeAnnotation | None:
        """Get the type annotation for a given key."""
        if key in self.fields:
            return self.fields[key]
        return self.extra_items

    def get_required(self, key: str) -> bool:
        """Check if a key is required in this dict type."""
        if key in self.fields:
            return key in self.required_fields
        if self.extra_items is not None:
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

    def _get_converter(self, key: str) -> Converter[Any, Any] | None:
        """Get the converter for a key, or None if the key should be dropped."""
        if key in self._field_converters:
            return self._field_converters[key]
        return self._extra_converter

    def _check_required_fields(self, result: dict[Any, Any]) -> None:
        """Raise TypeError if any required field is missing from result."""
        missing = next(
            (
                k
                for k in self._field_converters
                if k not in result and self._target_info.get_required(k)
            ),
            None,
        )
        if missing:
            raise TypeError(f"Missing required key '{missing}' for {self._target_info.tp}")

    def convert(self, source: dict) -> dict:
        result = {
            key: conv.convert(value)
            for key, value in source.items()
            if (conv := self._get_converter(key))
        }
        self._check_required_fields(result)
        return result

    def safe_convert(self, source: dict) -> dict:
        result = {
            key: conv.safe_convert(value)
            for key, value in source.items()
            if (conv := self._get_converter(key))
        }
        self._check_required_fields(result)
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

        source_is_dict = isinstance(source_origin, type) and issubclass(source_origin, dict)
        target_is_dict = isinstance(target_origin, type) and issubclass(target_origin, dict)

        return source_is_dict and target_is_dict

    def _resolve_field_converters(
        self, source_info: DictInfo, target_info: DictInfo, registry: ConverterRegistry
    ) -> dict[str, Converter[Any, Any]]:
        """Resolve converters for all fields. Raises _IncompatibleTypes on failure."""
        all_keys = source_info.fields.keys() | target_info.fields.keys()

        # Check for required fields that source can't provide
        if any(
            target_info.get_required(k)
            for k in all_keys
            if source_info.get_tp(k) is None and target_info.get_tp(k) is not None
        ):
            raise _IncompatibleTypes()

        # Build converters for keys where both have types
        converters = {
            k: conv
            for k in all_keys
            if (src := source_info.get_tp(k))
            and (tgt := target_info.get_tp(k))
            and (conv := registry.resolve(src.tp, tgt.tp))
        }

        # Check all expected converters were found (none resolved to None)
        expected = sum(
            1
            for k in all_keys
            if source_info.get_tp(k) is not None and target_info.get_tp(k) is not None
        )
        if len(converters) != expected:
            raise _IncompatibleTypes()

        return converters

    def _resolve_extra_converter(
        self, source_info: DictInfo, target_info: DictInfo, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        """Resolve extra items converter. Raises _IncompatibleTypes on failure."""
        if source_info.extra_items is None or target_info.extra_items is None:
            return None
        conv = registry.resolve(source_info.extra_items.tp, target_info.extra_items.tp)
        if conv is None:
            raise _IncompatibleTypes()
        return conv

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        source_stripped = unwrap(source_tp)
        target_stripped = unwrap(target_tp)

        source_info = DictInfo.create(source_stripped)
        target_info = DictInfo.create(target_stripped)

        if registry.resolve(source_info.key_type, target_info.key_type) is None:
            return None

        try:
            field_converters = self._resolve_field_converters(source_info, target_info, registry)
            extra_converter = self._resolve_extra_converter(source_info, target_info, registry)
        except _IncompatibleTypes:
            return None

        return DictConverter(target_info, field_converters, extra_converter)
