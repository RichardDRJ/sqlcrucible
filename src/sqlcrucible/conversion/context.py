"""Context handed to value converters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConversionContext:
    """Context handed to ``ConvertToSAWith`` / ``ConvertFromSAWith`` callables.

    ``target_type`` is the *resolved* entity-side field type — for a concrete
    specialisation of a generic entity it's the specialised type, not the
    ``TypeVar`` — so a converter can validate against it (e.g. with
    ``pydantic.TypeAdapter``) without having to guess. New fields can be added
    here as more context is needed; the callable signature stays
    ``Callable[[Any, ConversionContext], Any]``.
    """

    target_type: Any
