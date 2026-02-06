"""Type matching utilities for polymorphic type resolution.

This module provides utilities for measuring the "distance" between types
in an inheritance hierarchy. This is used during polymorphic loading to
select the most specific entity class that matches a given SQLAlchemy model.

Example:
    Given classes Animal -> Dog -> Poodle, and an SA model of type PoodleAutoModel:
    - mro_distance(PoodleAutoModel, AnimalAutoModel) = 2
    - mro_distance(PoodleAutoModel, DogAutoModel) = 1
    - mro_distance(PoodleAutoModel, PoodleAutoModel) = 0

    The entity with the smallest distance (Poodle, distance=0) is chosen.
"""

from logging import getLogger
from typing import Any


logger = getLogger(__name__)

# Distance values for edge cases. These are deliberately large numbers so that:
# 1. Normal MRO distances (typically 0-10) are clearly distinguishable
# 2. Comparisons using min() will prefer any real inheritance relationship
# 3. NOT_SUBCLASS is larger than NOT_FOUND because NOT_FOUND implies the types
#    ARE related (issubclass passed), just that something unexpected happened

#: Distance returned when two types have no inheritance relationship at all.
#: This is the largest possible distance, indicating the types are unrelated.
NOT_SUBCLASS_DISTANCE = 100_000

#: Distance returned when issubclass() passes but the ancestor isn't found in
#: the MRO. This shouldn't happen in normal operation and likely indicates a
#: bug or unusual metaclass behavior.
NOT_FOUND_IN_MRO_DISTANCE = 10_000


def mro_distance(tp1: type[Any], tp2: type[Any]) -> int:
    """Calculate the inheritance distance between two types.

    Returns the number of steps in the Method Resolution Order (MRO) from
    the descendant type to the ancestor type. This is used to find the
    most specific type match in polymorphic scenarios.

    Args:
        tp1: First type to compare.
        tp2: Second type to compare.

    Returns:
        - 0 if tp1 is tp2
        - Positive integer representing MRO distance if one is an ancestor of the other
        - NOT_SUBCLASS_DISTANCE (100,000) if the types are unrelated
        - NOT_FOUND_IN_MRO_DISTANCE (10,000) if issubclass passes but MRO lookup fails

    Example::

        class A:
            pass


        class B(A):
            pass


        class C(B):
            pass


        mro_distance(C, A)  # Returns 2
        mro_distance(C, C)  # Returns 0
        mro_distance(A, C)  # Returns 2 (A is ancestor of C)
    """
    if issubclass(tp1, tp2):
        descendent = tp1
        ancestor = tp2
    elif issubclass(tp2, tp1):
        descendent = tp2
        ancestor = tp1
    else:
        return NOT_SUBCLASS_DISTANCE

    for idx, it in enumerate(descendent.__mro__):
        if it is ancestor:
            return idx

    logger.warning(
        "Trying to find MRO distance from %s to %s but ancestor not found in mro",
        descendent,
        ancestor,
    )
    return NOT_FOUND_IN_MRO_DISTANCE
