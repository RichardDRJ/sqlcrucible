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
    - Target is Any (accepts anything, pass through)
    - Source is Any AND target is also Any

    Note: Any -> T is NOT valid because we cannot prove Any is compatible with T.
    T -> Any IS valid because T is a subtype of Any.

    TypedDict targets are excluded since they don't support isinstance checks,
    which the NoOpConverter relies on for runtime validation.
    """
    source_tp = unwrap(source_tp)
    target_tp = unwrap(target_tp)

    # TypedDict doesn't support isinstance, so can't use NoOp
    if is_typeddict(target_tp):
        return False

    # T -> Any is valid (T is subtype of Any)
    # Any -> Any is also valid
    if target_tp is Any:
        return True

    # Any -> T is NOT valid (can't prove Any is T)
    if source_tp is Any:
        return False

    source_is_not_generic = get_origin(source_tp) is None
    return source_is_not_generic and source_tp is target_tp
