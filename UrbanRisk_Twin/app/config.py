from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")

BACKEND_PORT = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "5000")))

DEBUG = os.getenv("DEBUG", "true").lower() == "true"

USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
USE_CLOUD_STORAGE = os.getenv("USE_CLOUD_STORAGE", "false").lower() == "true"

PROJECT_ID = (
    os.getenv("PROJECT_ID")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or "urbanrisk-twin-local"
)

FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "urban_risk_zones")
FIRESTORE_METADATA_COLLECTION = os.getenv(
    "FIRESTORE_METADATA_COLLECTION",
    "urban_risk_metadata"
)

BUCKET_NAME = os.getenv("BUCKET_NAME", "")
CLOUD_STORAGE_PREFIX = os.getenv("CLOUD_STORAGE_PREFIX", "urbanrisk-twin")