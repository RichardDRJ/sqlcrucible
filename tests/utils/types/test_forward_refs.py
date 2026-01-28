"""Tests for forward reference resolution utilities."""

import pytest

from sqlcrucible.utils.types.forward_refs import resolve_forward_refs


class Target:
    pass


class Owner:
    pass


@pytest.mark.parametrize(
    ("tp", "expected"),
    [
        pytest.param("Target", Target, id="simple_string_ref"),
        pytest.param(list["Target"], list[Target], id="list_of_forward_ref"),
        pytest.param(dict[str, "Target"], dict[str, Target], id="dict_with_forward_ref_value"),
        pytest.param(
            dict[str, list["Target"]],
            dict[str, list[Target]],
            id="nested_generic_forward_ref",
        ),
        pytest.param(
            list["Target"] | None,
            list[Target] | None,
            id="union_with_forward_ref",
        ),
    ],
)
def test_resolve_forward_refs(tp: object, expected: object) -> None:
    """Forward references are resolved in various type positions."""
    assert resolve_forward_refs(tp, Owner) == expected


def test_resolve_already_resolved_type() -> None:
    """Already-resolved types pass through unchanged."""
    assert resolve_forward_refs(list[Target], Owner) == list[Target]


def test_resolve_plain_type() -> None:
    """Plain types without forward refs pass through unchanged."""
    assert resolve_forward_refs(str, Owner) is str
