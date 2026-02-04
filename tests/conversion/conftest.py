from dataclasses import dataclass
from typing import Any

import pytest

from sqlcrucible.conversion import default_registry
from sqlcrucible.conversion.registry import Converter, ConverterRegistry


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

    def convert(self, source: SourceItem) -> TargetItem:
        return TargetItem(value=source.value * 2)

    def safe_convert(self, source: SourceItem) -> TargetItem:
        return self.convert(source)


class TargetToSourceConverter(Converter[TargetItem, SourceItem]):
    """Converts TargetItem to SourceItem."""

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return source_tp is TargetItem and target_tp is SourceItem

    def convert(self, source: TargetItem) -> SourceItem:
        return SourceItem(value=source.value // 2)

    def safe_convert(self, source: TargetItem) -> SourceItem:
        return self.convert(source)


@pytest.fixture
def registry() -> ConverterRegistry:
    """Create a registry with standard converters plus custom test converter."""
    registry = ConverterRegistry(
        SourceToTargetConverter(),
        TargetToSourceConverter(),
        *default_registry,
    )
    return registry
