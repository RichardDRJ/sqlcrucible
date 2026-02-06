"""Utilities for resolving forward references in type annotations."""

from __future__ import annotations

import sys
from types import UnionType
from typing import Any, ForwardRef, Union, get_args, get_origin, get_type_hints

from typing_extensions import evaluate_forward_ref


def resolve_forward_refs(tp: Any, owner: type) -> Any:
    """Recursively resolve forward references in a type annotation.

    Uses the stdlib's get_type_hints() to handle recursive resolution of
    forward references in parameterized types like list["Book"] or
    dict[str, "Entity"].

    Args:
        tp: The type to resolve, which may contain forward references.
        owner: The class that provides the namespace context for resolution.

    Returns:
        The type with all forward references resolved to actual types.

    Example::

        class Book:
            pass


        class Library:
            books: list["Book"]


        resolve_forward_refs(list["Book"], Library)  # Returns list[Book]
    """
    # Create a temporary class with the type as an annotation.
    # get_type_hints() will recursively resolve all forward refs using
    # the owner's module namespace for lookups.
    temp = type(
        "_ForwardRefResolver",
        (),
        {"__annotations__": {"_": tp}, "__module__": owner.__module__},
    )
    globalns = vars(sys.modules[owner.__module__])
    localns = vars(owner)
    hints = get_type_hints(temp, globalns=globalns, localns=localns)
    return hints["_"]


def evaluate_forward_refs(tp: Any, owner: type[object]) -> Any:
    """Recursively evaluate ForwardRef objects in a type annotation.

    Unlike resolve_forward_refs which uses get_type_hints(), this function
    directly evaluates ForwardRef objects using evaluate_forward_ref(). It
    handles string annotations, ForwardRef instances, and recursively processes
    generic type arguments.

    Args:
        tp: The type to evaluate, which may contain ForwardRef objects or strings.
        owner: The class that provides the namespace context for evaluation.

    Returns:
        The type with all ForwardRef objects evaluated to actual types.
    """
    if isinstance(tp, str):
        forward_ref = ForwardRef(tp)
        return evaluate_forward_ref(forward_ref, owner=owner)

    if isinstance(tp, ForwardRef):
        return evaluate_forward_ref(tp, owner=owner)

    origin = get_origin(tp)
    args = get_args(tp)

    if origin is None:
        return tp

    evaluated_args = tuple(evaluate_forward_refs(arg, owner) for arg in args)

    # `UnionType` can't be subscripted - we need to use `Union` instead
    if origin is UnionType:
        origin = Union
    return origin[evaluated_args] if evaluated_args else tp
