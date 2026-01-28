"""Utilities for resolving forward references in type annotations."""

from __future__ import annotations

import sys
from typing import Any, get_type_hints


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
