from __future__ import annotations

from dataclasses import dataclass, field
from types import GenericAlias
from typing import Annotated, Any, Literal, Protocol, get_args, get_origin


class TypeTransformer(Protocol):
    def matches(self, annotation: Any) -> bool: ...

    def apply(
        self,
        annotation: Any,
        chain: TypeTransformerChain,
    ) -> TypeTransformerResult: ...


class AnnotatedTypeTransformer(TypeTransformer):
    def matches(self, annotation: Any) -> bool:
        return get_origin(annotation) is Annotated

    def apply(
        self,
        annotation: Any,
        chain: TypeTransformerChain,
    ) -> TypeTransformerResult:
        tp, *annotations = get_args(annotation)
        inner = chain.apply(tp)
        return TypeTransformerResult(
            result=Annotated[inner.result, *annotations],
            additional_globals=inner.additional_globals,
        )


class GenericTypeTransformer(TypeTransformer):
    def matches(self, annotation: Any) -> bool:
        return isinstance(annotation, GenericAlias)

    def apply(
        self,
        annotation: Any,
        chain: TypeTransformerChain,
    ) -> TypeTransformerResult:
        tp = get_origin(annotation)
        args = get_args(annotation)
        inner = chain.apply(tp)
        return TypeTransformerResult(
            result=Annotated[inner.result, *args],
            additional_globals=inner.additional_globals,
        )


class LiteralTypeTransformer(TypeTransformer):
    def matches(self, annotation: Any) -> bool:
        return get_origin(annotation) is Literal

    def apply(
        self,
        annotation: Any,
        chain: TypeTransformerChain,
    ) -> TypeTransformerResult:
        return TypeTransformerResult(result=annotation)


@dataclass
class TypeTransformerResult:
    """Result of transforming a type annotation.

    Contains the transformed type and any additional globals needed
    for the type to be evaluable (e.g., forward references).
    """

    result: Any
    """The transformed annotation."""

    additional_globals: dict[str, Any] = field(default_factory=dict)
    """Additional globals needed to evaluate the result type."""


class TypeTransformerChain:
    DEFAULT_TRANSFORMERS: list[TypeTransformer] = [
        AnnotatedTypeTransformer(),
        GenericTypeTransformer(),
        LiteralTypeTransformer(),
    ]

    def __init__(self, transformers: list[TypeTransformer]):
        self._transformers = transformers

    def apply(self, annotation: Any) -> TypeTransformerResult:
        for transformer in self._transformers:
            if transformer.matches(annotation):
                return transformer.apply(annotation, self)
        return TypeTransformerResult(result=annotation)
