from typing import Generic, Any, Callable, TypeVar

E = TypeVar('E')


class Node(Generic[E]):
    def __init__(self, key: int, data: E) -> None:
        self.data: int = data
        self.key: int = key
        self.next: Node[E] = None
        self.prev: Node[E] = None
