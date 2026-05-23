from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import database


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "ttk.sqlite3"
DEFAULT_STATIC_DIR = ROOT


def create_handler(db_path: str | Path, static_dir: str | Path = DEFAULT_STATIC_DIR):
    db_path = Path(db_path)
    static_dir = Path(static_dir).resolve()
    database.init_db(db_path)

    class TtkRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/activities":
                self._send_json({"activities": database.list_activities(db_path)})
                return

            self._serve_static(static_dir)

        def do_POST(self) -> None:
            path = self._path_parts()
            body = self._read_json()

            try:
                if path == ["api", "activities"]:
                    activity = database.create_activity(db_path, body.get("name", ""))
                    self._send_json(activity, status=201)
                    return

                if len(path) == 4 and path[:2] == ["api", "activities"]:
                    activity_id = int(path[2])
                    if path[3] == "roles":
                        item = database.add_role(db_path, activity_id, body.get("name", ""))
                        self._send_json(item, status=201)
                        return
                    if path[3] == "members":
                        item = database.add_member(db_path, activity_id, body.get("name", ""))
                        self._send_json(item, status=201)
                        return
            except ValueError:
                self._send_json({"error": "invalid id"}, status=400)
                return
            except database.ValidationError as error:
                self._send_json({"error": str(error)}, status=400)
                return
            except database.NotFoundError as error:
                self._send_json({"error": str(error)}, status=404)
                return

            self._send_json({"error": "not found"}, status=404)

        def do_DELETE(self) -> None:
            path = self._path_parts()

            try:
                if len(path) == 3 and path[:2] == ["api", "activities"]:
                    database.delete_activity(db_path, int(path[2]))
                    self._send_empty()
                    return

                if len(path) == 5 and path[:2] == ["api", "activities"]:
                    activity_id = int(path[2])
                    item_id = int(path[4])
                    if path[3] == "roles":
                        database.delete_role(db_path, activity_id, item_id)
                        self._send_empty()
                        return
                    if path[3] == "members":
                        database.delete_member(db_path, activity_id, item_id)
                        self._send_empty()
                        return
            except ValueError:
                self._send_json({"error": "invalid id"}, status=400)
                return
            except database.NotFoundError as error:
                self._send_json({"error": str(error)}, status=404)
                return

            self._send_json({"error": "not found"}, status=404)

        def log_message(self, format: str, *args) -> None:
            return

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}

            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                raise database.ValidationError("request body must be valid JSON")

            if not isinstance(parsed, dict):
                raise database.ValidationError("request body must be a JSON object")
            return parsed

        def _path_parts(self) -> list[str]:
            path = urlparse(self.path).path.strip("/")
            return [unquote(part) for part in path.split("/") if part]

        def _serve_static(self, static_root: Path) -> None:
            parsed_path = urlparse(self.path).path
            requested = "index.html" if parsed_path in ("", "/") else parsed_path.lstrip("/")
            target = (static_root / requested).resolve()

            if static_root not in target.parents and target != static_root:
                self._send_json({"error": "not found"}, status=404)
                return

            if not target.is_file():
                self._send_json({"error": "not found"}, status=404)
                return

            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(target.read_bytes())

        def _send_json(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_empty(self, status: int = 204) -> None:
            self.send_response(status)
            self.end_headers()

    return TtkRequestHandler


def run(host: str = "127.0.0.1", port: int = 8000, db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    handler = create_handler(db_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"ttk is running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

