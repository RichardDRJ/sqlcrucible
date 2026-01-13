"""SAType utility for type-safe access to entity SQLAlchemy types."""

from typing import Protocol, TypeVar

_S = TypeVar("_S", covariant=True)


class HasSAType(Protocol[_S]):
    """Protocol for types that have a __sqlalchemy_type__ property."""

    @property
    def __sqlalchemy_type__(self) -> _S: ...


class SATypeMeta(type):
    """Metaclass that enables SAType[Entity] subscript syntax."""

    def __getitem__(cls, item: HasSAType[_S]) -> _S:
        return item.__sqlalchemy_type__


class SAType(metaclass=SATypeMeta):
    """Utility to access an entity's SQLAlchemy type.

    Provides a cleaner syntax for accessing an entity's SQLAlchemy type:

    ```python
    # Instead of:
    select(Track.__sqlalchemy_type__).where(Track.__sqlalchemy_type__.length_seconds > 180)

    # Write:
    select(SAType[Track]).where(SAType[Track].length_seconds > 180)
    ```

    With generated stubs, type checkers know the exact return type and
    can provide autocompletion for column names.
    """

    @classmethod
    def __class_getitem__(cls, item: HasSAType[_S]) -> _S:
        return item.__sqlalchemy_type__
