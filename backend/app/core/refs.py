"""Firestore collection reference builders, shared across routers.

Hierarchy: organizations/{org_id}/farms/{farm_id}/houses/{house_id}/...
"""

from google.cloud.firestore import Client, CollectionReference


def farms_ref(db: Client, org_id: str) -> CollectionReference:
    return db.collection("organizations").document(org_id).collection("farms")


def houses_ref(db: Client, org_id: str, farm_id: str) -> CollectionReference:
    return farms_ref(db, org_id).document(farm_id).collection("houses")


def flocks_ref(db: Client, org_id: str, farm_id: str, house_id: str) -> CollectionReference:
    return houses_ref(db, org_id, farm_id).document(house_id).collection("flocks")


def flock_checks_ref(db: Client, org_id: str, farm_id: str, house_id: str) -> CollectionReference:
    return houses_ref(db, org_id, farm_id).document(house_id).collection("flock_checks")


def inspections_ref(db: Client, org_id: str, farm_id: str, house_id: str) -> CollectionReference:
    return houses_ref(db, org_id, farm_id).document(house_id).collection("inspections")


def alerts_ref(db: Client, org_id: str) -> CollectionReference:
    return db.collection("organizations").document(org_id).collection("alerts")


def organization_ref(db: Client, org_id: str):
    return db.collection("organizations").document(org_id)


def members_ref(db: Client, org_id: str) -> CollectionReference:
    return organization_ref(db, org_id).collection("members")


def invitations_ref(db: Client, org_id: str) -> CollectionReference:
    return organization_ref(db, org_id).collection("invitations")


def subscription_ref(db: Client, org_id: str):
    """Single document (`current`) rather than a bare field on the org
    document, so future plan-history/upgrade records have a natural place
    to live alongside it without another schema change."""
    return organization_ref(db, org_id).collection("subscription").document("current")


def agent_runs_ref(db: Client, org_id: str) -> CollectionReference:
    return organization_ref(db, org_id).collection("agent_runs")


def agent_recommendations_ref(db: Client, org_id: str) -> CollectionReference:
    return organization_ref(db, org_id).collection("agent_recommendations")


# Poultry reference knowledge (RAG) is curated, global, and NOT
# organization-scoped - every org retrieves from the same approved
# knowledge base. See app/services/knowledge_service.py.
def knowledge_documents_ref(db: Client) -> CollectionReference:
    return db.collection("knowledge_documents")


def knowledge_chunks_ref(db: Client) -> CollectionReference:
    return db.collection("knowledge_chunks")
