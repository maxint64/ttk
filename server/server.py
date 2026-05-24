from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import DEFAULT_DB_PATH, DEFAULT_STATIC_DIR
from . import database


MAX_TEXT_LENGTH = 144


def create_app(
    db_path: str | Path = DEFAULT_DB_PATH,
    static_dir: str | Path = DEFAULT_STATIC_DIR,
) -> FastAPI:
    db_path = Path(db_path)
    static_dir = Path(static_dir).resolve()
    database.init_db(db_path)

    app = FastAPI(title="ttk")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, error: HTTPException
    ) -> JSONResponse:
        if isinstance(error.detail, dict):
            return JSONResponse(error.detail, status_code=error.status_code)
        return JSONResponse({"error": error.detail}, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse({"error": "request body must be valid JSON"}, status_code=400)

    @app.get("/api/activities")
    async def list_activities() -> dict[str, list[dict[str, Any]]]:
        return {"activities": database.list_activities(db_path)}

    @app.post("/api/activities", status_code=201)
    async def create_activity(body: Any = Body(default=None)) -> dict[str, Any]:
        body = _read_json_object(body)
        try:
            return database.create_activity(db_path, _read_text(body, "name"))
        except database.ValidationError as error:
            raise _api_error(400, str(error)) from error

    @app.delete("/api/activities/{activity_id}", status_code=204, response_class=Response)
    async def delete_activity(activity_id: str) -> Response:
        try:
            database.delete_activity(db_path, _parse_id(activity_id))
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return Response(status_code=204)

    @app.post("/api/activities/{activity_id}/roles", status_code=201)
    async def add_role(activity_id: str, body: Any = Body(default=None)) -> dict[str, Any]:
        return _add_activity_item(db_path, activity_id, body, database.add_role)

    @app.post("/api/activities/{activity_id}/members", status_code=201)
    async def add_member(activity_id: str, body: Any = Body(default=None)) -> dict[str, Any]:
        body = _read_json_object(body)
        try:
            return database.add_member(
                db_path,
                _parse_id(activity_id),
                _read_text(body, "name"),
                _read_email(body, "email"),
            )
        except database.ValidationError as error:
            raise _api_error(400, str(error)) from error
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error

    @app.delete(
        "/api/activities/{activity_id}/roles/{role_id}",
        status_code=204,
        response_class=Response,
    )
    async def delete_role(activity_id: str, role_id: str) -> Response:
        _delete_activity_item(db_path, activity_id, role_id, database.delete_role)
        return Response(status_code=204)

    @app.delete(
        "/api/activities/{activity_id}/members/{member_id}",
        status_code=204,
        response_class=Response,
    )
    async def delete_member(activity_id: str, member_id: str) -> Response:
        _delete_activity_item(db_path, activity_id, member_id, database.delete_member)
        return Response(status_code=204)

    @app.get("/api/activities/{activity_id}/assignments")
    async def list_assignments(activity_id: str) -> dict[str, list[dict[str, Any]]]:
        try:
            assignments = database.list_assignments(db_path, _parse_id(activity_id))
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return {"assignments": assignments}

    @app.get("/api/activities/{activity_id}/assignments/dates/{assigned_on}")
    async def list_assignments_on(
        activity_id: str, assigned_on: str
    ) -> dict[str, list[dict[str, Any]]]:
        try:
            assignments = database.list_assignments_on(
                db_path,
                _parse_id(activity_id),
                _clean_date(assigned_on, "assigned_on"),
            )
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return {"assignments": assignments}

    @app.post("/api/activities/{activity_id}/assignments", status_code=201)
    async def add_assignment(
        activity_id: str, body: Any = Body(default=None)
    ) -> dict[str, Any]:
        body = _read_json_object(body)
        try:
            return database.add_assignment(
                db_path,
                _parse_id(activity_id),
                _read_body_id(body, "role_id"),
                _read_body_id(body, "member_id"),
                _read_optional_date(body, "assigned_on"),
            )
        except database.ValidationError as error:
            raise _api_error(400, str(error)) from error
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error

    @app.delete(
        "/api/activities/{activity_id}/assignments/{assignment_id}",
        status_code=204,
        response_class=Response,
    )
    async def delete_assignment(activity_id: str, assignment_id: str) -> Response:
        try:
            database.delete_assignment(
                db_path, _parse_id(activity_id), _parse_id(assignment_id)
            )
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return Response(status_code=204)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api_not_found(path: str) -> None:
        raise _api_error(404, "not found")

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


def _read_json_object(parsed: Any) -> dict[str, Any]:
    if parsed is None:
        return {}

    if not isinstance(parsed, dict):
        raise _api_error(400, "request body must be a JSON object")
    return parsed


def _add_activity_item(
    db_path: Path,
    activity_id: str,
    parsed_body: Any,
    add_item: Callable[[Path, int, str], dict[str, Any]],
) -> dict[str, Any]:
    body = _read_json_object(parsed_body)
    try:
        return add_item(db_path, _parse_id(activity_id), _read_text(body, "name"))
    except database.ValidationError as error:
        raise _api_error(400, str(error)) from error
    except database.NotFoundError as error:
        raise _api_error(404, str(error)) from error


def _delete_activity_item(db_path: Path, activity_id: str, item_id: str, delete_item) -> None:
    try:
        delete_item(db_path, _parse_id(activity_id), _parse_id(item_id))
    except database.NotFoundError as error:
        raise _api_error(404, str(error)) from error


def _parse_id(value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise _api_error(400, "invalid id") from error


def _read_body_id(body: dict[str, Any], key: str) -> int:
    if key not in body:
        raise _api_error(400, f"{key} is required")
    return _parse_id(str(body[key]))


def _read_text(body: dict[str, Any], key: str) -> str:
    return _clean_text(body.get(key, ""), key)


def _read_email(body: dict[str, Any], key: str) -> str:
    cleaned = _clean_text(body.get(key, ""), key).lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise _api_error(400, f"{key} must be valid")
    return cleaned


def _clean_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise _api_error(400, f"{field_name} must be text")

    if any(unicodedata.category(character).startswith("C") for character in value):
        raise _api_error(400, f"{field_name} contains invalid characters")

    cleaned = value.strip()
    if not cleaned:
        raise _api_error(400, f"{field_name} is required")
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise _api_error(400, f"{field_name} must be {MAX_TEXT_LENGTH} characters or fewer")
    return cleaned


def _read_optional_date(body: dict[str, Any], key: str) -> str | None:
    if key not in body or body[key] is None:
        return None
    if not isinstance(body[key], str):
        raise _api_error(400, f"{key} must be text")
    return _clean_date(body[key], key)


def _clean_date(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise _api_error(400, f"{field_name} is required")
    try:
        date.fromisoformat(cleaned)
    except ValueError as error:
        raise _api_error(400, f"{field_name} must be a valid YYYY-MM-DD date") from error
    return cleaned


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": message})


def run(host: str = "127.0.0.1", port: int = 8000, db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"ttk is running at http://{host}:{port}")
    uvicorn.run(create_app(db_path), host=host, port=port)


if __name__ == "__main__":
    run()
