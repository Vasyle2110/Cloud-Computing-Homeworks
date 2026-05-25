import json
from datetime import datetime, timezone

from google.cloud import storage

from app.config import PROJECT_ID, BUCKET_NAME, CLOUD_STORAGE_PREFIX


def get_storage_client() -> storage.Client:
    return storage.Client(project=PROJECT_ID)


def upload_live_zones_backup(zones: list[dict], metadata: dict | None = None) -> dict:
    """
    Salvează un backup JSON în Cloud Storage.
    Nu suprascrie fișierele vechi. Creează un obiect cu timestamp.
    """
    if not BUCKET_NAME:
        return {
            "status": "skipped",
            "target": "cloud_storage",
            "reason": "BUCKET_NAME is not configured"
        }

    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    blob_name = (
        f"{CLOUD_STORAGE_PREFIX}/live-zones/"
        f"iasi_zones_live_{timestamp}.json"
    )

    payload = {
        "metadata": metadata or {},
        "zones": zones
    }

    blob = bucket.blob(blob_name)

    blob.upload_from_string(
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json"
    )

    return {
        "status": "uploaded",
        "target": "cloud_storage",
        "bucket": BUCKET_NAME,
        "object": blob_name,
        "count": len(zones)
    }