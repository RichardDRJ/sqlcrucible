from dataclasses import dataclass
from typing import Any

import pytest

from sqlcrucible.conversion import default_registry
from sqlcrucible.conversion.context import ConversionContext
from sqlcrucible.conversion.registry import Converter, ConverterRegistry

#: A throwaway context for converter unit tests — the converters under test
#: here don't consult ``target_type``, so its value is irrelevant.
ANY_CONTEXT = ConversionContext(target_type=Any)


@dataclass(frozen=True)
class SourceItem:
    value: int


@dataclass(frozen=True)
class TargetItem:
    value: int


class SourceToTargetConverter(Converter[SourceItem, TargetItem]):
    """Converts SourceItem to TargetItem."""

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return source_tp is SourceItem and target_tp is TargetItem

    def convert(self, source: SourceItem, context: ConversionContext) -> TargetItem:
        return TargetItem(value=source.value * 2)

    def safe_convert(self, source: SourceItem, context: ConversionContext) -> TargetItem:
        return self.convert(source, context)


class TargetToSourceConverter(Converter[TargetItem, SourceItem]):
    """Converts TargetItem to SourceItem."""

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return source_tp is TargetItem and target_tp is SourceItem

    def convert(self, source: TargetItem, context: ConversionContext) -> SourceItem:
        return SourceItem(value=source.value // 2)

    def safe_convert(self, source: TargetItem, context: ConversionContext) -> SourceItem:
        return self.convert(source, context)


@pytest.fixture
def registry() -> ConverterRegistry:
    """Create a registry with standard converters plus custom test converter."""
    registry = ConverterRegistry(
        SourceToTargetConverter(),
        TargetToSourceConverter(),
        *default_registry,
    )
    return registry
