from typing import Any, List, Tuple

class SimpleEmbedder:
    """Tiny in-memory store + substring search. Swap for a vector DB later."""
    def __init__(self):
        self._store: List[Tuple[str, Any]] = []

    def store(self, key: str, value: Any) -> None:
        self._store.append((str(key), value))

    def search(self, query: str, k: int = 5) -> List[Any]:
        q = query.lower()
        hits = [v for k_, v in self._store if q in k_.lower()]
        return hits[:k]

    def all(self) -> List[Tuple[str, Any]]:
        return list(self._store)