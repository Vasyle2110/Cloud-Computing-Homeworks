import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

STORAGE_FILE = "storage.json"

def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def load_storage():
    if not os.path.exists(STORAGE_FILE):
        return {"tasks": [], "next_id": 1}
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "tasks" not in data or "next_id" not in data:
            return {"tasks": [], "next_id": 1}
        return data
    except (json.JSONDecodeError, OSError):
        raise

def save_storage(data):
    tmp = STORAGE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORAGE_FILE)

def find_task(data, task_id: int):
    for t in data["tasks"]:
        if t["id"] == task_id:
            return t
    return None

class RestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload=None, headers=None):
        body = b""
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None, "Empty body"
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8")), None
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "Invalid JSON"

    def _parse_path(self):
        path = urlparse(self.path).path
        if path == "/tasks":
            return ("collection", None, None)

        m_item = re.fullmatch(r"/tasks/(\d+)", path)
        if m_item:
            return ("item", int(m_item.group(1)), None)

        m_action = re.fullmatch(r"/tasks/(\d+)/([a-zA-Z0-9_-]+)", path)
        if m_action:
            return ("action", int(m_action.group(1)), m_action.group(2))

        return (None, None, None)

    # GET
    def do_GET(self):
        kind, task_id, action = self._parse_path()
        if kind is None:
            return self._send_json(404, {"error": "Not Found"})
        try:
            data = load_storage()
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage read failed"})

        if kind == "collection":
            q = parse_qs(urlparse(self.path).query)
            status_filter = q.get("status", [None])[0]
            limit = q.get("limit", [None])[0]
            offset = q.get("offset", [None])[0]

            tasks = data["tasks"]
            if status_filter in ("open", "done"):
                tasks = [t for t in tasks if t["status"] == status_filter]

            try:
                if offset is not None:
                    o = max(0, int(offset))
                    tasks = tasks[o:]
                if limit is not None:
                    l = max(0, int(limit))
                    tasks = tasks[:l]
            except ValueError:
                return self._send_json(400, {"error": "Bad Request", "details": "limit/offset must be integers"})

            return self._send_json(200, {"items": tasks, "count": len(tasks)})

        if kind == "item":
            task = find_task(data, task_id)
            if not task:
                return self._send_json(404, {"error": "Not Found", "details": f"Task {task_id} does not exist"})
            return self._send_json(200, task)

        if kind == "action":
            return self._send_json(405, {"error": "Method Not Allowed"})

    # POST
    def do_POST(self):
        kind, task_id, action = self._parse_path()
        if kind is None:
            return self._send_json(404, {"error": "Not Found"})
        try:
            data = load_storage()
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage read failed"})

        if kind == "collection":
            body, err = self._read_json()
            if err:
                return self._send_json(400, {"error": "Bad Request", "details": err})

            title = body.get("title")
            description = body.get("description", "")
            if not isinstance(title, str) or not title.strip():
                return self._send_json(400, {"error": "Bad Request", "details": "title is required (non-empty string)"})
            if not isinstance(description, str):
                return self._send_json(400, {"error": "Bad Request", "details": "description must be a string"})

            new_id = data["next_id"]
            data["next_id"] += 1

            task = {
                "id": new_id,
                "title": title.strip(),
                "description": description,
                "status": "open",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            data["tasks"].append(task)

            try:
                save_storage(data)
            except Exception:
                return self._send_json(500, {"error": "Internal Server Error", "details": "Storage write failed"})
            return self._send_json(
                201,
                task,
                headers={"Location": f"/tasks/{new_id}"}
            )

        if kind == "action":
            if action != "complete":
                return self._send_json(404, {"error": "Not Found"})

            task = find_task(data, task_id)
            if not task:
                return self._send_json(404, {"error": "Not Found", "details": f"Task {task_id} does not exist"})

            task["status"] = "done"
            task["updated_at"] = now_iso()

            try:
                save_storage(data)
            except Exception:
                return self._send_json(500, {"error": "Internal Server Error", "details": "Storage write failed"})

            return self._send_json(200, task)

        return self._send_json(405, {"error": "Method Not Allowed"})

    # PUT
    def do_PUT(self):
        kind, task_id, action = self._parse_path()
        if kind is None:
            return self._send_json(404, {"error": "Not Found"})

        try:
            data = load_storage()
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage read failed"})

        if kind == "collection":
            return self._send_json(405, {"error": "Method Not Allowed", "details": "Use PUT on /tasks/{id} to replace a task"})

        if kind == "action":
            return self._send_json(405, {"error": "Method Not Allowed"})

        body, err = self._read_json()
        if err:
            return self._send_json(400, {"error": "Bad Request", "details": err})

        title = body.get("title")
        description = body.get("description", "")
        status = body.get("status", "open")

        if not isinstance(title, str) or not title.strip():
            return self._send_json(400, {"error": "Bad Request", "details": "title is required (non-empty string)"})
        if not isinstance(description, str):
            return self._send_json(400, {"error": "Bad Request", "details": "description must be a string"})
        if status not in ("open", "done"):
            return self._send_json(400, {"error": "Bad Request", "details": "status must be 'open' or 'done'"})

        task = find_task(data, task_id)
        if not task:
            return self._send_json(404, {"error": "Not Found", "details": f"Task {task_id} does not exist"})

        task["title"] = title.strip()
        task["description"] = description
        task["status"] = status
        task["updated_at"] = now_iso()

        try:
            save_storage(data)
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage write failed"})

        return self._send_json(200, task)

    #  DELETE
    def do_DELETE(self):
        kind, task_id, action = self._parse_path()
        if kind is None:
            return self._send_json(404, {"error": "Not Found"})
        try:
            data = load_storage()
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage read failed"})

        if kind == "collection":
            return self._send_json(405, {"error": "Method Not Allowed", "details": "Deleting the entire collection is not supported"})

        if kind == "action":
            return self._send_json(405, {"error": "Method Not Allowed"})

        task = find_task(data, task_id)
        if not task:
            return self._send_json(404, {"error": "Not Found", "details": f"Task {task_id} does not exist"})

        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        try:
            save_storage(data)
        except Exception:
            return self._send_json(500, {"error": "Internal Server Error", "details": "Storage write failed"})

        return self._send_json(204, None)

    def log_message(self, format, *args):
        return


def main():
    host = "127.0.0.1"
    port = 8000
    httpd = HTTPServer((host, port), RestHandler)
    print(f"Server running at http://{host}:{port}")
    print("Routes: /tasks, /tasks/{id}, /tasks/{id}/complete")
    httpd.serve_forever()

if __name__ == "__main__":
    main()