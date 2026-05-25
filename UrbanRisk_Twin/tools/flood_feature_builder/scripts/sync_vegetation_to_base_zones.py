import csv
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
BUILDER_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[3]

VEGETATION_CSV = BUILDER_ROOT / "data" / "vegetation_features.csv"
BASE_ZONES_JSON = PROJECT_ROOT / "data" / "iasi_zones_base.json"


def load_vegetation_index_by_zone(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"Nu exista CSV-ul de vegetatie: {csv_path}")

    result = {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "zone_id",
            "vegetation_index",
            "confidence",
            "sources_used",
        }

        missing_columns = required_columns - set(reader.fieldnames or [])

        if missing_columns:
            raise ValueError(
                f"CSV-ul de vegetatie nu are coloanele necesare: {missing_columns}"
            )

        for row in reader:
            zone_id = row["zone_id"].strip()

            if not zone_id:
                continue

            try:
                vegetation_index = float(row["vegetation_index"])
            except ValueError:
                raise ValueError(
                    f"vegetation_index invalid pentru zona {zone_id}: "
                    f"{row['vegetation_index']}"
                )

            if vegetation_index < 0 or vegetation_index > 1:
                raise ValueError(
                    f"vegetation_index trebuie sa fie intre 0 si 1 pentru {zone_id}. "
                    f"Valoare gasita: {vegetation_index}"
                )

            result[zone_id] = {
                "vegetation_index": round(vegetation_index, 4),
                "vegetation_confidence": row.get("confidence", "").strip(),
                "vegetation_sources_used": row.get("sources_used", "").strip(),
            }

    return result


def load_base_zones(json_path: Path):
    if not json_path.exists():
        raise FileNotFoundError(f"Nu exista fisierul de zone: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_zones_container(data):
    """
    Accepta doua forme posibile:
    1. lista directa:
       [
         {"zone_id": "..."}
       ]

    2. obiect cu cheia zones:
       {
         "zones": [
           {"zone_id": "..."}
         ]
       }
    """

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
    print("UrbanRisk Twin - Sync vegetation_index to base zones")
    print("=" * 80)

    print(f"Vegetation CSV: {VEGETATION_CSV}")
    print(f"Base zones JSON: {BASE_ZONES_JSON}")

    vegetation_by_zone = load_vegetation_index_by_zone(VEGETATION_CSV)
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

        vegetation_data = vegetation_by_zone.get(zone_id)

        if vegetation_data is None:
            missing_in_csv.append(zone_id)
            continue

        old_value = zone.get("vegetation_index")
        new_value = vegetation_data["vegetation_index"]

        zone["vegetation_index"] = new_value
        zone["vegetation_source"] = "tools/flood_feature_builder/data/vegetation_features.csv"
        zone["vegetation_confidence"] = vegetation_data["vegetation_confidence"]
        zone["vegetation_sources_used"] = vegetation_data["vegetation_sources_used"]
        zone["vegetation_last_updated"] = used_timestamp

        updated_count += 1

        print(
            f"{zone_id}: vegetation_index {old_value} -> {new_value} "
            f"({vegetation_data['vegetation_confidence']})"
        )

    save_json(base_data, BASE_ZONES_JSON)

    print()
    print(f"Backup creat: {backup_path}")
    print(f"Zone actualizate: {updated_count}/{len(zones)}")

    if missing_in_csv:
        print("Zone lipsa in vegetation_features.csv:")
        for zone_id in missing_in_csv:
            print(f"- {zone_id}")

    print("=" * 80)


if __name__ == "__main__":
    main()