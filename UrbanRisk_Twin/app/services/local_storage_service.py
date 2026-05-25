import json
from pathlib import Path
from typing import Any

from app.config import DATA_DIR


def read_json_file(file_path: Path) -> Any:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json_file(file_path: Path, data: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_base_zones() -> list[dict]:
    return read_json_file(DATA_DIR / "iasi_zones_base.json")


def load_live_zones() -> list[dict]:
    live_file = DATA_DIR / "iasi_zones_live.json"

    if live_file.exists():
        return read_json_file(live_file)

    return load_base_zones()


def save_live_zones(data: list[dict]) -> None:
    write_json_file(DATA_DIR / "iasi_zones_live.json", data)


def save_processed_risks(data: list[dict]) -> None:
    write_json_file(DATA_DIR / "processed_risks.json", data)


def save_ingestion_status(status: dict) -> None:
    write_json_file(DATA_DIR / "ingestion_status.json", status)


def load_ingestion_status() -> dict:
    status_file = DATA_DIR / "ingestion_status.json"

    if not status_file.exists():
        return {
            "status": "not_started",
            "message": "No ingestion has been executed yet."
        }

    return read_json_file(status_file)