from typing import Annotated, Required, NotRequired
from uuid import UUID

import pytest
from sqlalchemy.orm import Mapped

from sqlcrucible.utils.types.annotations import TypeAnnotation, unwrap


@pytest.mark.parametrize(
    ("annotation", "expected_tp"),
    [
        (str, str),
        (int, int),
        (UUID, UUID),
        (list[int], list[int]),
        (dict[str, int], dict[str, int]),
    ],
)
def test_create_extracts_plain_type(annotation, expected_tp):
    result = TypeAnnotation.create(annotation)
    assert result.tp == expected_tp
    assert result.qualifiers == ()
    assert result.metadata == ()


@pytest.mark.parametrize(
    ("annotation", "expected_tp", "expected_qualifier"),
    [
        (Mapped[str], str, Mapped),
        (Mapped[UUID], UUID, Mapped),
        (Mapped[list[int]], list[int], Mapped),
        (Required[str], str, Required),
        (Required[int], int, Required),
        (NotRequired[str], str, NotRequired),
        (NotRequired[int], int, NotRequired),
    ],
)
def test_create_extracts_type_from_single_qualifier(annotation, expected_tp, expected_qualifier):
    result = TypeAnnotation.create(annotation)
    assert result.tp == expected_tp
    assert expected_qualifier in result.qualifiers


@pytest.mark.parametrize(
    ("annotation", "expected_tp"),
    [
        (Mapped[Required[str]], str),  # ty:ignore[invalid-type-form]
        (Mapped[NotRequired[int]], int),  # ty:ignore[invalid-type-form]
        (Required[Mapped[UUID]], UUID),
    ],
)
def test_create_extracts_type_from_nested_qualifiers(annotation, expected_tp):
    result = TypeAnnotation.create(annotation)
    assert result.tp is expected_tp


def test_create_extracts_metadata_from_annotated():
    annotation = Annotated[str, "some_metadata", 123]
    result = TypeAnnotation.create(annotation)
    assert result.tp is str
    assert result.metadata == ("some_metadata", 123)


def test_create_handles_annotated_with_qualifier():
    annotation = Annotated[Mapped[str], "metadata"]
    result = TypeAnnotation.create(annotation)
    assert result.tp is str
    assert Mapped in result.qualifiers
    assert result.metadata == ("metadata",)


def test_create_handles_qualifier_inside_annotated():
    annotation = Mapped[Annotated[str, "metadata"]]
    result = TypeAnnotation.create(annotation)
    assert result.tp is str
    assert Mapped in result.qualifiers
    assert result.metadata == ("metadata",)


# Tests for unwrap function


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (str, str),
        (int, int),
        (UUID, UUID),
        (list[int], list[int]),
        (dict[str, int], dict[str, int]),
    ],
)
def test_unwrap_returns_plain_types_unchanged(annotation, expected):
    assert unwrap(annotation) == expected


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (Mapped[str], str),
        (Mapped[UUID], UUID),
        (Mapped[list[int]], list[int]),
        (Required[str], str),
        (NotRequired[int], int),
    ],
)
def test_unwrap_removes_single_qualifier(annotation, expected):
    assert unwrap(annotation) == expected


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (Mapped[Required[str]], str),  # ty:ignore[invalid-type-form]
        (Mapped[NotRequired[int]], int),  # ty:ignore[invalid-type-form]
        (Required[Mapped[UUID]], UUID),
    ],
)
def test_unwrap_removes_nested_qualifiers(annotation, expected):
    assert unwrap(annotation) is expected


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (Annotated[str, "metadata"], str),
        (Annotated[int, "a", "b"], int),
        (Annotated[UUID, 123], UUID),
    ],
)
def test_unwrap_removes_annotated(annotation, expected):
    assert unwrap(annotation) is expected


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (Annotated[Mapped[str], "metadata"], str),
        (Mapped[Annotated[int, "metadata"]], int),
        (Annotated[Mapped[Required[UUID]], "meta"], UUID),  # ty:ignore[invalid-type-form]
    ],
)
def test_unwrap_removes_combined_wrappers(annotation, expected):
    assert unwrap(annotation) is expected
