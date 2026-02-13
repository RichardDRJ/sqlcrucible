from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

from sqlcrucible.conversion.registry import Converter

IdentityMap = dict[int, Any]

_active_identity_map: ContextVar[IdentityMap | None] = ContextVar(
    "_active_identity_map",
    default=None,
)


@contextmanager
def _identity_map(identity_map: IdentityMap | None = None) -> Generator[IdentityMap]:
    if identity_map is None:
        existing = _active_identity_map.get()
        identity_map = existing if existing is not None else {}
    token = _active_identity_map.set(identity_map)
    try:
        yield identity_map
    finally:
        _active_identity_map.reset(token)


class CachingConverter(Converter[Any, Any]):
    """Converter wrapper that checks the identity map before delegating.

    Wraps an inner converter with a lookup into the active identity map
    (a dict keyed by ``id(source)``). If the source has already been
    converted within the current conversion tree, the cached result is
    returned directly.
    """

    def __init__(self, inner: Converter[Any, Any]) -> None:
        self._inner = inner

    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        return self._inner.matches(source_tp, target_tp)

    def convert(self, source: Any) -> Any:
        identity_map = _active_identity_map.get()
        if identity_map is not None:
            cached = identity_map.get(id(source))
            if cached is not None:
                return cached
        return self._inner.convert(source)

    def safe_convert(self, source: Any) -> Any:
        identity_map = _active_identity_map.get()
        if identity_map is not None:
            cached = identity_map.get(id(source))
            if cached is not None:
                return cached
        return self._inner.safe_convert(source)
