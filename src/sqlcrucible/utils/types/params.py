from typing import Any, get_args, get_origin


def _get_type_params_for_base(tp: Any, base: type) -> tuple[Any, ...] | None:
    """Internal implementation of get_type_params_for_base."""
    origin = get_origin(tp) or tp
    args = get_args(tp) or ()

    if origin is base:
        return args

    params = getattr(origin, "__parameters__", ())
    substitutions = dict(zip(params, args, strict=True)) if args else {}

    for orig_base in getattr(origin, "__orig_bases__", ()):
        base_origin = get_origin(orig_base) or orig_base
        base_args = get_args(orig_base)
        resolved_base_args = tuple(substitutions.get(arg, arg) for arg in base_args)
        resolved_base = base_origin[resolved_base_args] if resolved_base_args else base_origin
        base_resolution = _get_type_params_for_base(resolved_base, base)
        if base_resolution is not None:
            return base_resolution

    return None


def get_type_params_for_base(tp: Any, base: type) -> tuple[Any, ...]:
    """Extract type parameters for a base type from a parameterized type.

    Given a potentially parameterized type and a base type, return the type
    parameters for the base type as seen from the parameterized type.

    Args:
        tp: A potentially parameterized type (e.g., list[int], MyDict[str, int]).
        base: The base type to extract parameters for (e.g., list, dict).

    Returns:
        A tuple of type parameters for the base type.

    Raises:
        TypeError: If tp is not a subclass of base.

    Examples:
        >>> get_type_params_for_base(list[int], list)
        (<class 'int'>,)

        >>> from typing import Generic, TypeVar
        >>> K = TypeVar("K")
        >>> V = TypeVar("V")
        >>> class MyDict(dict[K, V], Generic[K, V]): ...
        >>> get_type_params_for_base(MyDict[str, int], dict)
        (<class 'str'>, <class 'int'>)

        >>> class MySubDict(MyDict[str, int]): ...
        >>> get_type_params_for_base(MySubDict, dict)
        (<class 'str'>, <class 'int'>)
    """
    result = _get_type_params_for_base(tp, base)
    if result is None:
        raise TypeError(f"Type {tp} is not a subclass of {base}")
    return result
