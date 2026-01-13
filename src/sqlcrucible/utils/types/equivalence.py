import typing
from typing import Any, get_args, get_origin

import sqlalchemy.orm


def strip_wrappers(tp: Any) -> Any:
    """Recursively strip known wrappers from a type when they don't affect the actual resolved type.

    Args:
        tp: The type to unwrap.

    Returns:
        The unwrapped type.
    """
    match get_origin(tp), get_args(tp):
        case typing.Annotated, (wrapped_tp, *_):
            return strip_wrappers(wrapped_tp)
        case sqlalchemy.orm.Mapped, (wrapped_tp, *_):
            return strip_wrappers(wrapped_tp)
        case _:
            return tp


def types_are_non_parameterised_and_equal(source_tp: Any, target_tp: Any) -> bool:
    source_tp = strip_wrappers(source_tp)
    target_tp = strip_wrappers(target_tp)
    source_is_not_generic = get_origin(source_tp) is None
    return source_is_not_generic and source_tp is target_tp
