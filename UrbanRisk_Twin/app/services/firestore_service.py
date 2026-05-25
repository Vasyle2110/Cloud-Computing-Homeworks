from typing import Any

from google.cloud import firestore

from app.config import (
    PROJECT_ID,
    FIRESTORE_COLLECTION,
    FIRESTORE_METADATA_COLLECTION
)


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)


def save_zones_to_firestore(zones: list[dict]) -> dict:
    """
    Salvează zonele actualizate în Firestore.
    Document ID = zone_id.
    """
    client = get_firestore_client()
    collection_ref = client.collection(FIRESTORE_COLLECTION)

    batch = client.batch()

    for zone in zones:
        zone_id = zone.get("zone_id")

        if not zone_id:
            continue

        doc_ref = collection_ref.document(zone_id)
        batch.set(doc_ref, zone)

    batch.commit()

    return {
        "status": "saved",
        "target": "firestore",
        "collection": FIRESTORE_COLLECTION,
        "count": len(zones)
    }


def load_zones_from_firestore() -> list[dict]:
    """
    Citește zonele din Firestore.
    Dacă nu există documente, returnează listă goală.
    """
    client = get_firestore_client()
    docs = client.collection(FIRESTORE_COLLECTION).stream()

    zones = []

    for doc in docs:
        zone = doc.to_dict()
        zones.append(zone)

    return sorted(zones, key=lambda item: item.get("name", ""))


def save_ingestion_status_to_firestore(status: dict[str, Any]) -> dict:
    client = get_firestore_client()

    doc_ref = (
        client
        .collection(FIRESTORE_METADATA_COLLECTION)
        .document("latest_ingestion")
    )

    doc_ref.set(status)

    return {
        "status": "saved",
        "target": "firestore",
        "collection": FIRESTORE_METADATA_COLLECTION,
        "document": "latest_ingestion"
    }


def load_ingestion_status_from_firestore() -> dict | None:
    client = get_firestore_client()

    doc_ref = (
        client
        .collection(FIRESTORE_METADATA_COLLECTION)
        .document("latest_ingestion")
    )

    snapshot = doc_ref.get()

    if not snapshot.exists:
        return None

    return snapshot.to_dict()