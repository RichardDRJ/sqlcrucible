"""Type conversion registry and protocols.

This module defines the core abstractions for SQLCrucible's type conversion
system. The system uses a registry of converters and converter factories to
transform values between entity fields and SQLAlchemy model attributes.

Key concepts:
    - Converter: Transforms a value from one type to another
    - ConverterFactory: Creates converters for specific type pairs
    - ConverterRegistry: Resolves the appropriate converter for a type pair

The registry is queried in order, returning the first matching converter.
Factories can recursively query the registry to handle nested types (e.g.,
list[CustomType] needs a converter for CustomType).
"""

from typing import Any, Protocol, TypeVar, runtime_checkable

_I = TypeVar("_I", contravariant=True)
_O = TypeVar("_O", covariant=True)


@runtime_checkable
class Converter(Protocol[_I, _O]):
    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        """Check if this converter can handle the given type pair.

        Args:
            source_tp: The source type.
            target_tp: The target type.

        Returns:
            True if this converter can convert from source_tp to target_tp.
        """
        ...

    def convert(self, source: _I) -> _O:
        """Convert a value from source type to target type.

        Args:
            source: The value to convert.

        Returns:
            The converted value.
        """
        ...


@runtime_checkable
class ConverterFactory(Protocol[_I, _O]):
    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        """Check if this factory can create a converter for the given type pair.

        Args:
            source_tp: The source type.
            target_tp: The target type.

        Returns:
            True if this factory can create a converter for this type pair.
        """
        ...

    def converter(
        self, source_tp: Any, target_tp: Any, registry: "ConverterRegistry"
    ) -> Converter[_I, _O] | None:
        """Create a converter for the given type pair.

        Args:
            source_tp: The source type.
            target_tp: The target type.
            registry: The converter registry for resolving nested types.

        Returns:
            A Converter that can handle the type pair.
        """
        ...


#: A registry entry can be either a direct Converter or a ConverterFactory
ConverterRegistryEntry = ConverterFactory[Any, Any] | Converter[Any, Any]

_T = TypeVar("_T")


class ConverterRegistry:
    """Registry that resolves converters for type pairs.

    The registry holds a sequence of converters and factories. When resolving
    a type pair, it queries each entry in order and returns the first one
    that matches and successfully produces a converter.

    Factories can recursively query this registry to resolve nested types,
    enabling conversion of complex types like list[CustomType] or dict[str, CustomType].

    Attributes:
        _converters: Ordered sequence of converters and factories to query.
    """

    def __init__(self, *converters: ConverterRegistryEntry) -> None:
        self._converters = converters

    def resolve(self, source_tp: Any, target_tp: Any) -> Converter[Any, Any] | None:
        """Find a converter for the given type pair.

        Iterates through registered converters/factories in order, returning
        the first one that matches and produces a non-None converter.

        Args:
            source_tp: The source type annotation.
            target_tp: The target type annotation.

        Returns:
            A Converter if one is found, None otherwise.
        """
        return next(
            (
                converter
                for entry in self._converters
                if entry.matches(source_tp, target_tp)
                and (
                    converter := (
                        entry
                        if isinstance(entry, Converter)
                        else entry.converter(source_tp, target_tp, self)
                    )
                )
            ),
            None,
        )

    def __iter__(self):
        return iter(self._converters)
