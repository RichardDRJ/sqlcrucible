"""Collection utility functions."""

from functools import reduce
from typing import Iterable, TypeVar

K = TypeVar("K")
V = TypeVar("V")


def group_pairs(pairs: Iterable[tuple[K, V]]) -> dict[K, list[V]]:
    """Group (key, value) pairs into a dict of lists by key.

    Args:
        pairs: An iterable of (key, value) tuples.

    Returns:
        A dict mapping each unique key to a list of its associated values.

    Example:
        >>> group_pairs([("a", 1), ("b", 2), ("a", 3)])
        {'a': [1, 3], 'b': [2]}
    """

    def accumulate(groups: dict[K, list[V]], pair: tuple[K, V]) -> dict[K, list[V]]:
        key, value = pair
        groups.setdefault(key, []).append(value)
        return groups

    return reduce(accumulate, pairs, {})
