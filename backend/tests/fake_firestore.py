"""Minimal in-memory stand-in for google.cloud.firestore.Client.

Supports exactly the surface app/core/refs.py and the route/service modules
actually use: collection/document chaining, get/set/update, and
where(field, "==", value) + order_by(...) + limit(n) + stream(). Good
enough to unit-test the Alert Engine and farm-context/comparison logic
without real GCP credentials or a Firestore emulator.

Not a Firestore reimplementation - only "==" filtering is supported, which
is all this codebase's queries use (composite-index-avoidance was a
deliberate choice - see comments in alerts.py/ask.py).
"""

from __future__ import annotations

import uuid

from google.cloud.firestore import Query


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeQuery:
    def __init__(self, store: dict, path: tuple, filters=None, order=None, limit_n=None):
        self._store = store
        self._path = path
        self._filters = filters or []
        self._order = order
        self._limit_n = limit_n

    def where(self, field, op, value):
        if op != "==":
            raise NotImplementedError("FakeFirestore only supports '==' filters")
        return FakeQuery(self._store, self._path, self._filters + [(field, value)], self._order, self._limit_n)

    def order_by(self, field, direction=Query.ASCENDING):
        return FakeQuery(self._store, self._path, self._filters, (field, direction), self._limit_n)

    def limit(self, n):
        return FakeQuery(self._store, self._path, self._filters, self._order, n)

    def stream(self):
        prefix_len = len(self._path)
        results = []
        for doc_path, data in self._store.items():
            if len(doc_path) != prefix_len + 1 or doc_path[:prefix_len] != self._path:
                continue
            if all(data.get(field) == value for field, value in self._filters):
                results.append(FakeSnapshot(doc_path[-1], data))
        if self._order:
            field, direction = self._order
            results.sort(key=lambda s: s.to_dict().get(field) or "", reverse=(direction == Query.DESCENDING))
        if self._limit_n is not None:
            results = results[: self._limit_n]
        return iter(results)

    def document(self, doc_id: str | None = None):
        doc_id = doc_id or uuid.uuid4().hex
        return FakeDocumentRef(self._store, self._path + (doc_id,))


class FakeDocumentRef:
    def __init__(self, store: dict, path: tuple):
        self._store = store
        self._path = path

    @property
    def id(self):
        return self._path[-1]

    def collection(self, name: str) -> FakeQuery:
        return FakeQuery(self._store, self._path + (name,))

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self._path[-1], self._store.get(self._path))

    def set(self, data: dict) -> None:
        self._store[self._path] = dict(data)

    def update(self, updates: dict) -> None:
        existing = dict(self._store.get(self._path, {}))
        existing.update(updates)
        self._store[self._path] = existing

    def delete(self) -> None:
        self._store.pop(self._path, None)


class FakeFirestoreClient:
    """Drop-in replacement for `Client` in `Depends(get_firestore_client)`."""

    def __init__(self):
        self._store: dict[tuple, dict] = {}

    def collection(self, name: str) -> FakeQuery:
        return FakeQuery(self._store, (name,))
