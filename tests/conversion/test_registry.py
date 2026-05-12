from typing import Any

from sqlcrucible.conversion.context import ConversionContext
from sqlcrucible.conversion.registry import Converter, ConverterRegistry

from tests.conversion.conftest import ANY_CONTEXT


def test_registry_returns_none_when_no_match() -> None:
    registry = ConverterRegistry()
    assert registry.resolve(int, str) is None


def test_registry_returns_first_matching_converter() -> None:
    class AlwaysMatchConverter(Converter[Any, Any]):
        def __init__(self, result: Any) -> None:
            self._result = result

        def matches(self, source_tp: Any, target_tp: Any) -> bool:
            return True

        def convert(self, source: Any, context: ConversionContext) -> Any:
            return self._result

        def safe_convert(self, source: Any, context: ConversionContext) -> Any:
            return self.convert(source, context)

    first_converter = AlwaysMatchConverter("first")
    second_converter = AlwaysMatchConverter("second")

    registry = ConverterRegistry(first_converter, second_converter)

    conv = registry.resolve(int, str)
    assert conv is not None
    assert conv is first_converter
    assert conv.convert(42, ANY_CONTEXT) == "first"
