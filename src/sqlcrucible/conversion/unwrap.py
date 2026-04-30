"""Converter factory for unwrapping transparent type wrappers."""

from typing import Annotated, Any, get_args, get_origin

from sqlalchemy.orm import Mapped

from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry

_WRAPPER_ORIGINS = (Annotated, Mapped)


def _unwrap(tp: Any) -> Any:
    """Strip a single Annotated[T, ...] or Mapped[T] wrapper, returning the inner type."""
    if get_origin(tp) in _WRAPPER_ORIGINS:
        return get_args(tp)[0]
    return tp


class AnnotatedUnwrappingFactory(ConverterFactory):
    """Factory that strips Annotated[T, ...] and Mapped[T] wrappers before converter lookup.

    Non-SQLCrucible annotations (e.g. access-control markers) and SQLAlchemy's
    Mapped wrapper should be transparent to the conversion registry. This factory
    unwraps them and delegates to the registry for the inner type pair.
    """

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return _unwrap(source_tp) is not source_tp or _unwrap(target_tp) is not target_tp

    def converter(
        self,
        source_tp: Any,
        target_tp: Any,
        registry: ConverterRegistry,
    ) -> Converter | None:
        return registry.resolve(_unwrap(source_tp), _unwrap(target_tp))
