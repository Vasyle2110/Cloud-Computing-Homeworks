import csv
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
BUILDER_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[3]

URBAN_DENSITY_CSV = BUILDER_ROOT / "data" / "urban_density_features.csv"
BASE_ZONES_JSON = PROJECT_ROOT / "data" / "iasi_zones_base.json"


def load_urban_density_by_zone(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"Nu exista CSV-ul de urban density: {csv_path}")

    result = {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "zone_id",
            "urban_density",
            "confidence",
            "sources_used",
        }

        missing_columns = required_columns - set(reader.fieldnames or [])

        if missing_columns:
            raise ValueError(
                f"CSV-ul de urban density nu are coloanele necesare: {missing_columns}"
            )

        for row in reader:
            zone_id = row["zone_id"].strip()

            if not zone_id:
                continue

            try:
                urban_density = float(row["urban_density"])
            except ValueError:
                raise ValueError(
                    f"urban_density invalid pentru zona {zone_id}: "
                    f"{row['urban_density']}"
                )

            if urban_density < 0 or urban_density > 1:
                raise ValueError(
                    f"urban_density trebuie sa fie intre 0 si 1 pentru {zone_id}. "
                    f"Valoare gasita: {urban_density}"
                )

            result[zone_id] = {
                "urban_density": round(urban_density, 4),
                "urban_density_confidence": row.get("confidence", "").strip(),
                "urban_density_sources_used": row.get("sources_used", "").strip(),
            }

    return result


def load_base_zones(json_path: Path):
    if not json_path.exists():
        raise FileNotFoundError(f"Nu exista fisierul de zone: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_zones_container(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("zones"), list):
        return data["zones"]

    raise ValueError(
        "Format necunoscut pentru iasi_zones_base.json. "
        "Ma asteptam la lista directa sau la obiect cu cheia 'zones'."
    )


def backup_file(path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.stem}.backup_{timestamp}{path.suffix}")

    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    return backup_path


def save_json(data, json_path: Path) -> None:
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def main() -> None:
    print("=" * 80)
    print("UrbanRisk Twin - Sync urban_density to base zones")
    print("=" * 80)

    print(f"Urban density CSV: {URBAN_DENSITY_CSV}")
    print(f"Base zones JSON: {BASE_ZONES_JSON}")

    urban_density_by_zone = load_urban_density_by_zone(URBAN_DENSITY_CSV)
    base_data = load_base_zones(BASE_ZONES_JSON)
    zones = extract_zones_container(base_data)

    backup_path = backup_file(BASE_ZONES_JSON)

    updated_count = 0
    missing_in_csv = []
    used_timestamp = datetime.now(timezone.utc).isoformat()

    for zone in zones:
        zone_id = zone.get("zone_id")

        if not zone_id:
            continue

        urban_density_data = urban_density_by_zone.get(zone_id)

        if urban_density_data is None:
            missing_in_csv.append(zone_id)
            continue

        old_value = zone.get("urban_density")
        new_value = urban_density_data["urban_density"]

        zone["urban_density"] = new_value
        zone["urban_density_source"] = "tools/flood_feature_builder/data/urban_density_features.csv"
        zone["urban_density_confidence"] = urban_density_data["urban_density_confidence"]
        zone["urban_density_sources_used"] = urban_density_data["urban_density_sources_used"]
        zone["urban_density_last_updated"] = used_timestamp

        updated_count += 1

        print(
            f"{zone_id}: urban_density {old_value} -> {new_value} "
            f"({urban_density_data['urban_density_confidence']})"
        )

    save_json(base_data, BASE_ZONES_JSON)

    print()
    print(f"Backup creat: {backup_path}")
    print(f"Zone actualizate: {updated_count}/{len(zones)}")

    if missing_in_csv:
        print("Zone lipsa in urban_density_features.csv:")
        for zone_id in missing_in_csv:
            print(f"- {zone_id}")

    print("=" * 80)


if __name__ == "__main__":
    main()