from typing import Any, get_origin

from typing_extensions import is_typeddict

from sqlcrucible.utils.types.annotations import unwrap


def types_are_non_parameterised_and_equal(source_tp: Any, target_tp: Any) -> bool:
    source_tp = unwrap(source_tp)
    target_tp = unwrap(target_tp)
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
    source_tp = unwrap(source_tp)
    target_tp = unwrap(target_tp)

    # TypedDict doesn't support isinstance, so can't use NoOp
    if is_typeddict(target_tp):
        return False

    if source_tp is Any or target_tp is Any:
        return True

    source_is_not_generic = get_origin(source_tp) is None
    return source_is_not_generic and source_tp is target_tp
