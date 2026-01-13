"""Function-based converter for custom type transformations.

This module provides a converter that wraps a user-supplied function to perform
type conversion. It's used when fields are annotated with ConvertToSAWith or
ConvertFromSAWith to specify custom conversion logic.

Example::

    converter = FunctionConverter(lambda x: x.total_seconds())
    converter.convert(timedelta(minutes=5))  # Returns 300.0
"""

from collections.abc import Callable
from typing import Any, TypeVar

from sqlcrucible.conversion.registry import Converter

_T = TypeVar("_T")
_R = TypeVar("_R")


class FunctionConverter(Converter[Any, Any]):
    """Converter that applies a custom function to transform values.

    This converter always reports that it matches any type pair, since the
    function itself determines what conversions are valid. Type checking
    is the responsibility of the wrapped function.

    Attributes:
        _fn: The conversion function to apply.
    """

    def __init__(self, fn: Callable[[_T], _R]):
        self._fn = fn

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return True

    def convert(self, source: Any) -> Any:
        return self._fn(source)
