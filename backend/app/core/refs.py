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
