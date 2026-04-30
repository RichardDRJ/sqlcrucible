"""SAType utility for type-safe access to entity SQLAlchemy types."""

from typing import Any, Protocol, TYPE_CHECKING, TypeVar

_S = TypeVar("_S")


class HasSAType(Protocol[_S]):
    """Protocol for entity classes that expose ``__sqlalchemy_type__``.

    The attribute is declared as ``ClassVar`` so that pyright accepts
    matching against entity classes whose own declarations use the
    same form (which SQLCrucibleBaseModel does). The metaclass
    accessor takes the class itself (``type[HasSAType[_S]]``) and reads
    the SA-type out at the class level.
    """

    __sqlalchemy_type__: _S


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

    if TYPE_CHECKING:

        def __setattr__(self, key: str, value: Any): ...
        def __getattr__(self, key: str) -> Any: ...
