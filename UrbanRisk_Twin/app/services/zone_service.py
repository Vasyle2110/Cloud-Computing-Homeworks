from app.config import USE_FIRESTORE
from app.services.local_storage_service import load_live_zones
from app.risk_engine.global_risk import build_risk_profile
from app.services.forecast_time_service import (
    apply_forecast_time_to_zone,
    strip_hourly_forecast_payload
)


def _load_zones_from_best_source() -> list[dict]:
    if USE_FIRESTORE:
        try:
            from app.services.firestore_service import load_zones_from_firestore

            firestore_zones = load_zones_from_firestore()

            if firestore_zones:
                return firestore_zones

        except Exception as exc:
            print(f"[WARN] Firestore read failed, falling back to local JSON: {exc}")

    return load_live_zones()


def get_all_zones(
    include_risk: bool = False,
    date: str | None = None,
    hour: str | int | None = None
) -> list[dict]:
    zones = _load_zones_from_best_source()

    prepared_zones = [
        apply_forecast_time_to_zone(
            zone=zone,
            date_value=date,
            hour_value=hour
        )
        for zone in zones
    ]

    if include_risk:
        return [
            strip_hourly_forecast_payload(build_risk_profile(zone))
            for zone in prepared_zones
        ]

    return [
        strip_hourly_forecast_payload(zone)
        for zone in prepared_zones
    ]


def get_zone_by_id(
    zone_id: str,
    include_risk: bool = True,
    date: str | None = None,
    hour: str | int | None = None
) -> dict | None:
    zones = _load_zones_from_best_source()

    for zone in zones:
        if zone.get("zone_id") == zone_id:
            prepared_zone = apply_forecast_time_to_zone(
                zone=zone,
                date_value=date,
                hour_value=hour
            )

            if include_risk:
                return strip_hourly_forecast_payload(
                    build_risk_profile(prepared_zone)
                )

            return strip_hourly_forecast_payload(prepared_zone)

    return None