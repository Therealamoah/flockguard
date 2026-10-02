"""Minimal in-memory stand-in for google.cloud.firestore.Client.

Supports exactly the surface app/core/refs.py and the route/service modules
actually use: collection/document chaining, get/set/update,
where(field, "==", value) + order_by(...) + limit(n) + stream(),
collection_group(name), and reference.parent/.parent chaining (used by
app/api/routes/team.py's collection-group invitation lookup). Good enough
to unit-test the app's Firestore-touching logic without real GCP
credentials or a Firestore emulator.

Not a Firestore reimplementation - only "==" filtering is supported, which
is all this codebase's queries use (composite-index-avoidance was a
deliberate choice - see comments in alerts.py/ask.py).
"""

from __future__ import annotations

import uuid

from google.cloud.firestore import Increment, Query


def _resolve_field(existing_value, new_value):
    """Resolves one field's write value against what's already stored -
    real Firestore's `Increment(n)` server-side transform is the only
    sentinel this codebase's writes use (app/services/usage_service.py)."""
    if isinstance(new_value, Increment):
        return (existing_value or 0) + new_value.value
    return new_value


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None, reference: "FakeDocumentRef | None" = None):
        self.id = doc_id
        self._data = data
        self.exists = data is not None
        self.reference = reference

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


# Firestore never matches a range filter against a missing field.
_OPS = {
    "==": lambda a, b: a == b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
}


def _matches(actual, op, expected) -> bool:
    return _OPS[op](actual, expected)


class FakeQuery:
    def __init__(self, store: dict, path: tuple, filters=None, order=None, limit_n=None):
        self._store = store
        self._path = path
        self._filters = filters or []
        self._order = order
        self._limit_n = limit_n

    @property
    def parent(self) -> "FakeDocumentRef | None":
        """The document containing this collection, or None for a
        top-level collection (mirrors CollectionReference.parent)."""
        if len(self._path) <= 1:
            return None
        return FakeDocumentRef(self._store, self._path[:-1])

    def where(self, field, op, value):
        if op not in _OPS:
            raise NotImplementedError(f"FakeFirestore does not support {op!r} filters")
        return FakeQuery(self._store, self._path, self._filters + [(field, op, value)], self._order, self._limit_n)

    def order_by(self, field, direction=Query.ASCENDING):
        return FakeQuery(self._store, self._path, self._filters, (field, direction), self._limit_n)

    def limit(self, n):
        return FakeQuery(self._store, self._path, self._filters, self._order, n)

    def _matching_docs(self, path_predicate) -> list[tuple[tuple, dict]]:
        matches = []
        for doc_path, data in self._store.items():
            if not path_predicate(doc_path):
                continue
            if all(_matches(data.get(field), op, value) for field, op, value in self._filters):
                matches.append((doc_path, data))
        return matches

    def stream(self):
        prefix_len = len(self._path)
        matches = self._matching_docs(
            lambda doc_path: len(doc_path) == prefix_len + 1 and doc_path[:prefix_len] == self._path
        )
        results = [
            FakeSnapshot(doc_path[-1], data, FakeDocumentRef(self._store, doc_path)) for doc_path, data in matches
        ]
        if self._order:
            field, direction = self._order
            results.sort(key=lambda s: s.to_dict().get(field) or "", reverse=(direction == Query.DESCENDING))
        if self._limit_n is not None:
            results = results[: self._limit_n]
        return iter(results)

    def document(self, doc_id: str | None = None):
        doc_id = doc_id or uuid.uuid4().hex
        return FakeDocumentRef(self._store, self._path + (doc_id,))


class FakeCollectionGroupQuery(FakeQuery):
    """Matches documents in ANY collection named `collection_id`, at any
    depth/parent - e.g. every organization's `invitations` subcollection at
    once, which is exactly what `db.collection_group("invitations")` does
    in real Firestore and what app/api/routes/team.py::my_invitations relies
    on to find a person's pending invites without knowing the org ahead of
    time.
    """

    def __init__(self, store: dict, collection_id: str, filters=None):
        super().__init__(store, (collection_id,), filters)
        self._collection_id = collection_id

    def where(self, field, op, value):
        if op != "==":
            raise NotImplementedError("FakeFirestore only supports '==' filters on collection groups")
        return FakeCollectionGroupQuery(self._store, self._collection_id, self._filters + [(field, op, value)])

    def stream(self):
        matches = self._matching_docs(lambda doc_path: len(doc_path) >= 2 and doc_path[-2] == self._collection_id)
        return iter(
            FakeSnapshot(doc_path[-1], data, FakeDocumentRef(self._store, doc_path)) for doc_path, data in matches
        )


class FakeDocumentRef:
    def __init__(self, store: dict, path: tuple):
        self._store = store
        self._path = path

    @property
    def id(self):
        return self._path[-1]

    @property
    def parent(self) -> FakeQuery:
        """The collection containing this document (mirrors DocumentReference.parent)."""
        return FakeQuery(self._store, self._path[:-1])

    def collection(self, name: str) -> FakeQuery:
        return FakeQuery(self._store, self._path + (name,))

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self._path[-1], self._store.get(self._path), self)

    def set(self, data: dict, merge: bool = False) -> None:
        existing = dict(self._store.get(self._path, {})) if merge else {}
        for field, value in data.items():
            existing[field] = _resolve_field(existing.get(field), value)
        self._store[self._path] = existing

    def update(self, updates: dict) -> None:
        existing = dict(self._store.get(self._path, {}))
        for field, value in updates.items():
            existing[field] = _resolve_field(existing.get(field), value)
        self._store[self._path] = existing

    def delete(self) -> None:
        self._store.pop(self._path, None)


class FakeFirestoreClient:
    """Drop-in replacement for `Client` in `Depends(get_firestore_client)`."""

    def __init__(self):
        self._store: dict[tuple, dict] = {}

    def collection(self, name: str) -> FakeQuery:
        return FakeQuery(self._store, (name,))

    def collection_group(self, collection_id: str) -> FakeCollectionGroupQuery:
        return FakeCollectionGroupQuery(self._store, collection_id)
