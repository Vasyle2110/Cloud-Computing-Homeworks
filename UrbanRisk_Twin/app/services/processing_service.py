from datetime import datetime, timezone

from app.services.zone_service import get_all_zones
from app.services.local_storage_service import save_processed_risks


def process_all_risks() -> dict:
    processed_zones = get_all_zones(include_risk=True)
    save_processed_risks(processed_zones)

    return {
        "status": "processed",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "count": len(processed_zones),
        "message": "Risk scores recalculated and saved locally.",
        "results": processed_zones
    }