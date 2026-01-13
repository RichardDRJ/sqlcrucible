from typing import Any, Callable, Generic, ParamSpec, TypeVar, cast

_T = TypeVar("_T")
_R = TypeVar("_R")

# Sentinel value for unset fields
UNSET = cast(Any, object())


class _lazyproperty(Generic[_T, _R]):
    """Descriptor that lazily computes a value once and caches it.

    Used for class-level properties that are expensive to compute and
    should only be computed once.

    Example:
        class MyClass:
            expensive_value: ClassVar[int | lazy_property[Self, int]]

            def __init_subclass__(cls):
                cls.expensive_value = lazy_property(lambda c: expensive_computation())
    """

    def __init__(self, func: Callable[[type[_T]], _R]) -> None:
        """Initialize with a function that computes the value.

        Args:
            func: Function that takes the owner class and returns the value.
        """
        self._func = func
        self._value: _R = UNSET

    def __get__(self, instance: Any, owner: type[_T]) -> _R:
        """Get the cached value, computing it on first access.

        Args:
            instance: The instance (unused, this is a class-level descriptor).
            owner: The owner class.

        Returns:
            The cached value.
        """
        if self._value is UNSET:
            self._value = self._func(owner)
        return self._value


def lazyproperty(func: Callable[[type[_T]], _R]) -> _R:
    return cast(_R, _lazyproperty(func))


_P = ParamSpec("_P")


class lazymethod(Generic[_T, _P, _R]):
    """Descriptor that lazily defines a method on a class.

    Used for methods which are dynamically defined using context which isn't available at
    class definition time.
    """

    def __init__(self, supplier: Callable[[type[_T]], Callable[_P, _R]]) -> None:
        self._supplier = supplier

    def __call__(self, wrapped: Callable[_P, _R]) -> Callable[_P, _R]:
        return cast(Callable[_P, _R], lazyproperty(self._supplier))
