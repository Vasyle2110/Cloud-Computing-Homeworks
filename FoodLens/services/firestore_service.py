from datetime import datetime, timezone
from google.cloud import firestore


class FirestoreService:
    def __init__(self, collection_name: str, project_id: str):
        self.client = firestore.Client(project=project_id)
        self.collection = self.client.collection(collection_name)

    def create_analysis_document(self, data: dict) -> str:
        payload = {
            **data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_ref = self.collection.document()
        doc_ref.set(payload)
        return doc_ref.id

    def update_analysis_document(self, doc_id: str, data: dict) -> None:
        payload = {
            **data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.collection.document(doc_id).update(payload)

    def get_analysis_document(self, doc_id: str) -> dict | None:
        doc = self.collection.document(doc_id).get()
        if not doc.exists:
            return None
        result = doc.to_dict()
        result["id"] = doc.id
        return result

    def list_analysis_documents(self, limit: int = 20) -> list[dict]:
        docs = (
            self.collection
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        results = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            results.append(item)
        return results