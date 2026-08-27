"""Generic type-safe registry primitive shared by the concrete registries."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Generic, TypeVar, cast, overload

T = TypeVar("T")
# Separate, unbounded var for the decorator form so the decorated object keeps
# its own concrete type instead of being narrowed to the registry's element type.
D = TypeVar("D")


class Registry(Generic[T]):
    """A simple name -> factory registry."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, T] = {}

    @overload
    def register(self, name: str) -> Callable[[D], D]: ...

    @overload
    def register(self, name: str, item: T) -> T: ...

    def register(self, name: str, item: T | None = None) -> Callable[[D], D] | T:
        """Register ``item`` under ``name``.

        Usable as a decorator (``@registry.register("x")``) or directly
        (``registry.register("x", value)``).
        """

        def _do(value: T) -> T:
            if name in self._items:
                raise ValueError(f"{self._kind} '{name}' is already registered.")
            self._items[name] = value
            return value

        if item is not None:
            return _do(item)
        return cast("Callable[[D], D]", _do)

    def get(self, name: str) -> T:
        if name not in self._items:
            raise KeyError(f"{self._kind} '{name}' is not registered.")
        return self._items[name]

    def names(self) -> list[str]:
        return sorted(self._items)

    def items(self) -> Iterable[tuple[str, T]]:
        return self._items.items()

    def __contains__(self, name: object) -> bool:
        return name in self._items
