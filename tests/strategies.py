"""Reusable Hypothesis strategies for SQLCrucible property-based tests."""

from dataclasses import dataclass
from typing import Annotated, Any, Literal

from hypothesis import strategies as st
from hypothesis.strategies import DrawFn

from sqlcrucible._types.annotations import DEFAULT_QUALIFIERS

# ---------------------------------------------------------------------------
# Literal helpers
# ---------------------------------------------------------------------------

LITERAL_VALUE_TYPES = (st.integers(), st.text(max_size=8), st.booleans())


@st.composite
def literal_values(
    draw: DrawFn,
    *,
    min_size: int = 1,
    max_size: int = 8,
) -> frozenset[int | str | bool]:
    """Generate a non-empty frozenset of literal-compatible values."""
    values = draw(
        st.frozensets(
            st.one_of(*LITERAL_VALUE_TYPES),
            min_size=min_size,
            max_size=max_size,
        )
    )
    return values


def make_literal_type(values: frozenset[Any]) -> Any:
    """Construct a ``Literal[v1, v2, ...]`` type at runtime.

    Uses ``Literal.__getitem__`` which is the standard subscript mechanism
    (``Literal[v1, v2]``), accessed via getattr to satisfy type checkers
    that don't model special form subscripting.
    """
    return Literal.__getitem__(tuple(values))  # pyright: ignore[reportAttributeAccessIssue]


@st.composite
def literal_subset_pair(
    draw: DrawFn,
) -> tuple[frozenset[Any], frozenset[Any]]:
    """Generate (source_values, target_values) where source ⊆ target.

    Returns two frozensets; the caller can build Literal types from them.
    """
    target = draw(literal_values(min_size=1, max_size=8))
    source = draw(
        st.frozensets(
            st.sampled_from(sorted(target, key=repr)),
            min_size=1,
            max_size=len(target),
        )
    )
    return source, target


@st.composite
def literal_non_subset_pair(
    draw: DrawFn,
) -> tuple[frozenset[Any], frozenset[Any]]:
    """Generate (source_values, target_values) where source ⊄ target.

    At least one element in source is guaranteed to not be in target.
    """
    target = draw(literal_values(min_size=1, max_size=6))
    extra_element = draw(st.one_of(*LITERAL_VALUE_TYPES).filter(lambda val: val not in target))
    target_list = sorted(target, key=repr)
    source_from_target = draw(
        st.frozensets(st.sampled_from(target_list), min_size=0, max_size=len(target))
    )
    source = source_from_target | {extra_element}
    return frozenset(source), target


# ---------------------------------------------------------------------------
# TypeAnnotation helpers
# ---------------------------------------------------------------------------

BASE_TYPES = st.sampled_from([int, str, float, bool, bytes, list[int], dict[str, int]])

QUALIFIER_WRAPPERS: list[Any] = list(DEFAULT_QUALIFIERS)


@st.composite
def wrapped_type(draw: DrawFn) -> tuple[Any, type, tuple[Any, ...], tuple[Any, ...]]:
    """Generate a base type wrapped in 0–3 qualifier/Annotated layers.

    Returns (wrapped_annotation, base_type, expected_qualifiers, expected_metadata).
    """
    base = draw(BASE_TYPES)
    annotation: Any = base
    qualifiers: list[Any] = []
    metadata: list[Any] = []

    num_layers = draw(st.integers(min_value=0, max_value=3))
    for _ in range(num_layers):
        action = draw(st.sampled_from(["qualifier", "annotated"]))
        if action == "qualifier":
            qualifier = draw(st.sampled_from(QUALIFIER_WRAPPERS))
            annotation = qualifier[annotation]
            qualifiers.insert(0, qualifier)
        else:
            meta_item = draw(st.text(min_size=1, max_size=5))
            annotation = Annotated[annotation, meta_item]
            metadata.append(meta_item)

    return annotation, base, tuple(qualifiers), tuple(metadata)


# ---------------------------------------------------------------------------
# Caching converter helpers
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """Simple test source for caching property tests."""

    value: int


@dataclass
class Target:
    """Simple test target for caching property tests."""

    value: int


@st.composite
def shared_object_list(
    draw: DrawFn,
    *,
    min_unique: int = 1,
    max_unique: int = 5,
    min_refs: int = 2,
    max_refs: int = 10,
) -> tuple[list[Source], list[Source]]:
    """Generate a list of Source objects with controlled sharing.

    Returns (reference_list, unique_objects) where reference_list may
    contain duplicate references to objects in unique_objects.
    """
    num_unique = draw(st.integers(min_value=min_unique, max_value=max_unique))
    unique_objects = [Source(value=ii) for ii in range(num_unique)]
    num_refs = draw(st.integers(min_value=min_refs, max_value=max_refs))
    indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=num_unique - 1),
            min_size=num_refs,
            max_size=num_refs,
        )
    )
    reference_list = [unique_objects[idx] for idx in indices]
    return reference_list, unique_objects
