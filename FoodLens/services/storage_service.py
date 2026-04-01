from datetime import datetime
from werkzeug.utils import secure_filename
from google.cloud import storage


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


class StorageService:
    def __init__(self, bucket_name: str, project_id: str):
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(bucket_name)

    def upload_image(self, file_storage, folder: str = "uploads") -> dict:
        original_name = secure_filename(file_storage.filename)
        extension = original_name.rsplit(".", 1)[1].lower()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        blob_name = f"{folder}/{timestamp}.{extension}"

        blob = self.bucket.blob(blob_name)
        blob.upload_from_file(file_storage.stream, content_type=file_storage.content_type)

        return {
            "blob_name": blob_name,
            "gs_uri": f"gs://{self.bucket.name}/{blob_name}",
            "public_url": blob.public_url,
            "original_name": original_name,
        }