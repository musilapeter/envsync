from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class InsertOneResult:
    inserted_id: int


class InMemoryCollection:
    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    async def find_one(
        self,
        query: dict[str, Any],
        sort: Optional[list[tuple[str, int]]] = None,
    ) -> Optional[dict[str, Any]]:
        matches = [doc for doc in self._documents if all(doc.get(key) == value for key, value in query.items())]
        if not matches:
            return None
        if sort:
            field_name, direction = sort[0]
            reverse = direction < 0
            matches.sort(key=lambda item: item.get(field_name, 0), reverse=reverse)
        return matches[0].copy()

    async def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        self._documents.append(document.copy())
        return InsertOneResult(inserted_id=len(self._documents) - 1)

    def clear(self) -> None:
        self._documents.clear()

    @property
    def documents(self) -> list[dict[str, Any]]:
        return [doc.copy() for doc in self._documents]


@dataclass
class Database:
    env_versions: InMemoryCollection = field(default_factory=InMemoryCollection)
    audits: InMemoryCollection = field(default_factory=InMemoryCollection)


db = Database()
