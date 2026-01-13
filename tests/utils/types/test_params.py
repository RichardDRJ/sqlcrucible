from typing import Generic, TypeVar

import pytest

from sqlcrucible.utils.types.params import get_type_params_for_base


@pytest.mark.parametrize(
    ("parameterized_type", "base", "expected"),
    [
        (list[int], list, (int,)),
        (list[str], list, (str,)),
        (set[float], set, (float,)),
        (dict[str, int], dict, (str, int)),
        (dict[int, list[str]], dict, (int, list[str])),
    ],
)
def test_parameterized_type_returns_type_args(parameterized_type, base, expected) -> None:
    assert get_type_params_for_base(parameterized_type, base) == expected


@pytest.mark.parametrize(
    ("unparameterized_type", "base"),
    [
        (list, list),
        (dict, dict),
        (set, set),
    ],
)
def test_unparameterized_type_returns_empty_tuple(unparameterized_type, base) -> None:
    assert get_type_params_for_base(unparameterized_type, base) == ()


def test_generic_subclass_preserves_typevar() -> None:
    T = TypeVar("T")

    class MyList(list[T], Generic[T]):
        pass

    result = get_type_params_for_base(MyList, list)
    assert result == (T,)


def test_parameterized_subclass_resolves_to_concrete_type() -> None:
    T = TypeVar("T")

    class MyList(list[T], Generic[T]):
        pass

    result = get_type_params_for_base(MyList[str], list)
    assert result == (str,)


def test_deeply_nested_inheritance_resolves_correctly() -> None:
    T = TypeVar("T")

    class MyList(list[T], Generic[T]):
        pass

    class MySubList(MyList[int]):
        pass

    result = get_type_params_for_base(MySubList, list)
    assert result == (int,)


def test_non_subclass_raises_type_error() -> None:
    with pytest.raises(TypeError, match="not a subclass"):
        get_type_params_for_base(str, list)
