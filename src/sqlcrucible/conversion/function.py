"""Function-based converter for custom type transformations.

This module provides a converter that wraps a user-supplied function to perform
type conversion. It's used when fields are annotated with ConvertToSAWith or
ConvertFromSAWith to specify custom conversion logic. The function is called as
``fn(value, context)``, where ``context`` is the
:class:`~sqlcrucible.conversion.context.ConversionContext` for the field being
converted (it carries the resolved field type).

Example::

    converter = FunctionConverter(lambda x, ctx: x.total_seconds())
    converter.convert(timedelta(minutes=5), ConversionContext(target_type=float))  # 300.0
"""

from collections.abc import Callable
from typing import Any

from sqlcrucible.conversion.context import ConversionContext
from sqlcrucible.conversion.registry import Converter


class FunctionConverter(Converter[Any, Any]):
    """Converter that applies a custom function to transform values.

    Reports a match for any type pair — the wrapped function decides what's
    valid; type checking is its responsibility. The function is invoked as
    ``fn(value, context)`` with the :class:`ConversionContext` supplied by the
    caller.
    """

    def __init__(self, fn: Callable[[Any, ConversionContext], Any]) -> None:
        self._fn = fn

    @property
    def fn(self) -> Callable[[Any, ConversionContext], Any]:
        return self._fn

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return True

    def convert(self, source: Any, context: ConversionContext) -> Any:
        return self._fn(source, context)

    def safe_convert(self, source: Any, context: ConversionContext) -> Any:
        return self.convert(source, context)
