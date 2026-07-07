from typing import Hashable, TypeVar

T = TypeVar("T", bound=Hashable)


def unique_preserve_order(items: list[T]) -> list[T]:
    """Return unique items in first-seen order."""
    return list(dict.fromkeys(items))
