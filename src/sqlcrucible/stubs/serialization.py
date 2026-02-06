"""Type annotation serialization for stub generation."""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from typing import Any, get_args, get_origin

from sqlalchemy.orm import Mapped


@dataclass(slots=True)
class TypeDef:
    """Represents a type definition with its required imports."""

    imports: list[str]
    type_def: str


def fqn(tp: type[Any]) -> str:
    """Get the fully qualified name for a type."""
    module = tp.__module__
    name = tp.__name__
    if module in ("builtins",):
        return name
    return f"{module}.{name}"


def to_typedef(ann: Any) -> TypeDef:
    """Convert a type annotation to a TypeDef with imports.

    Args:
        ann: The type annotation to convert.

    Returns:
        TypeDef with the string representation and required imports.
    """
    # Handle string annotations (forward references)
    if isinstance(ann, str):
        return TypeDef(imports=[], type_def=f'"{ann}"')

    # Handle None
    if ann is None or ann is type(None):
        return TypeDef(imports=[], type_def="None")

    origin = get_origin(ann)
    args = get_args(ann)

    match origin, args:
        case typing.Annotated, (tp, *_):
            return to_typedef(tp)
        case _ if origin is Mapped:
            return to_typedef((args or [Any])[0])
        case (types.UnionType, _) | (typing.Union, _):
            args_typedefs = [to_typedef(arg) for arg in args]
            all_imports = ["typing", *[imp for td in args_typedefs for imp in td.imports]]
            args_str = ", ".join(td.type_def for td in args_typedefs)
            return TypeDef(imports=all_imports, type_def=f"typing.Union[{args_str}]")
        case None, _:
            if isinstance(ann, type):
                if ann.__module__ == "builtins":
                    return TypeDef(imports=[], type_def=ann.__name__)
                return TypeDef(imports=[ann.__module__], type_def=fqn(ann))
            return TypeDef(imports=["typing"], type_def="typing.Any")

    # Generic type with origin and args
    origin_typedef = to_typedef(origin)
    args_typedefs = [to_typedef(arg) for arg in args]

    all_imports = [imp for td in (origin_typedef, *args_typedefs) for imp in td.imports]
    args_str = ", ".join(td.type_def for td in args_typedefs)

    # Use the origin's type_def (which is the short name)
    type_def = f"{origin_typedef.type_def}[{args_str}]"

    return TypeDef(imports=all_imports, type_def=type_def)
