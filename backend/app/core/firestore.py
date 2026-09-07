from functools import lru_cache

from firebase_admin import firestore as firebase_firestore
from google.cloud.firestore import Client

import app.core.firebase  # noqa: F401 - ensures the Firebase app is initialized first


@lru_cache
def get_firestore_client() -> Client:
    """Reuses the Firebase Admin app's own service-account credentials,
    rather than falling back to generic Application Default Credentials."""
    return firebase_firestore.client()
