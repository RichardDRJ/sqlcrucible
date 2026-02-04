import typing
from typing import Any, get_args, get_origin

import sqlalchemy.orm
from typing_extensions import is_typeddict


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


def types_are_noop_compatible(source_tp: Any, target_tp: Any) -> bool:
    """Check if types are compatible for a no-op conversion.

    Types are compatible if:
    - They are equal (after stripping wrappers and ignoring type params)
    - Source is Any (can be anything, pass through) AND target supports isinstance
    - Target is Any (accepts anything, pass through)

    TypedDict targets are excluded since they don't support isinstance checks,
    which the NoOpConverter relies on for runtime validation.
    """
    source_tp = strip_wrappers(source_tp)
    target_tp = strip_wrappers(target_tp)

    # TypedDict doesn't support isinstance, so can't use NoOp
    if is_typeddict(target_tp):
        return False

    if source_tp is Any or target_tp is Any:
        return True

    source_is_not_generic = get_origin(source_tp) is None
    return source_is_not_generic and source_tp is target_tp
