import typing
from sqlalchemy.orm import Mapped
from typing import Any, Required, NotRequired, get_origin, get_args, Self
from dataclasses import dataclass

DEFAULT_QUALIFIERS = (Mapped, Required, NotRequired)


@dataclass(frozen=True, kw_only=True, slots=True)
class TypeAnnotation:
    tp: type[Any]
    qualifiers: tuple[Any, ...]
    metadata: tuple[Any, ...]

    @classmethod
    def create(
        cls,
        annotation: Any,
        known_qualifiers: tuple[Any, ...] = DEFAULT_QUALIFIERS,
    ) -> Self:
        tp, qualifiers, metadata = cls._walk_tp(annotation, known_qualifiers)
        return cls(tp=tp, qualifiers=qualifiers, metadata=metadata)

    @classmethod
    def _walk_tp(
        cls,
        annotation: Any,
        known_qualifiers: tuple[Any, ...],
    ) -> tuple[Any, tuple[Any, ...], tuple[Any, ...]]:
        origin = get_origin(annotation)
        args = get_args(annotation)

        match origin, args:
            case typing.Annotated, (inner, *metadata):
                tp, inner_qualifiers, inner_metadata = cls._walk_tp(inner, known_qualifiers)
                return tp, inner_qualifiers, (*inner_metadata, *metadata)
            case qualifier, inner if qualifier in known_qualifiers:
                tp, inner_qualifiers, inner_metadata = cls._walk_tp(inner, known_qualifiers)
                return tp, (qualifier, *inner_qualifiers), inner_metadata
            case _:
                return annotation, (), ()
