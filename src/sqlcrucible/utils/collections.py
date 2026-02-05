"""Collection utility functions."""

from functools import reduce
from typing import Iterable, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")


def group_pairs(pairs: Iterable[tuple[_K, _V]]) -> dict[_K, list[_V]]:
    """Group (key, value) pairs into a dict of lists by key.

    Args:
        pairs: An iterable of (key, value) tuples.

    Returns:
        A dict mapping each unique key to a list of its associated values.

    Example:
        >>> group_pairs([("a", 1), ("b", 2), ("a", 3)])
        {'a': [1, 3], 'b': [2]}
    """

    def accumulate(groups: dict[_K, list[_V]], pair: tuple[_K, _V]) -> dict[_K, list[_V]]:
        key, value = pair
        groups.setdefault(key, []).append(value)
        return groups

    return reduce(accumulate, pairs, {})
