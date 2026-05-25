from __future__ import annotations

import atexit
import asyncio
import os
import threading
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import database, events
from .config import DEFAULT_DB_PATH, DEFAULT_PID_PATH, DEFAULT_STATIC_DIR
from .schemas import (
    ActivitiesResponse,
    ActivityResponse,
    AssignmentResponse,
    AssignmentsResponse,
    ErrorResponse,
    MemberResponse,
    RoleResponse,
)


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
        return JSONResponse(
            {"error": "リクエストのJSON形式が正しくありません。"}, status_code=400
        )

    error_responses = {
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    }

    @app.get(
        "/api/activities",
        response_model=ActivitiesResponse,
        responses=error_responses,
    )
    async def list_activities() -> ActivitiesResponse:
        return ActivitiesResponse(activities=database.list_activities(db_path))

    @app.get("/api/events")
    async def event_stream(request: Request) -> StreamingResponse:
        return StreamingResponse(
            stream_events(request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.post(
        "/api/activities",
        status_code=201,
        response_model=ActivityResponse,
        responses=error_responses,
    )
    async def create_activity(body: Any = Body(default=None)) -> ActivityResponse:
        body = _read_json_object(body)
        try:
            return ActivityResponse.model_validate(
                database.create_activity(db_path, _read_text(body, "name"))
            )
        except database.ValidationError as error:
            raise _api_error(400, str(error)) from error

    @app.delete("/api/activities/{activity_id}", status_code=204, response_class=Response)
    async def delete_activity(activity_id: str) -> Response:
        try:
            database.delete_activity(db_path, _parse_id(activity_id))
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return Response(status_code=204)

    @app.post(
        "/api/activities/{activity_id}/roles",
        status_code=201,
        response_model=RoleResponse,
        responses=error_responses,
    )
    async def add_role(activity_id: str, body: Any = Body(default=None)) -> RoleResponse:
        return RoleResponse.model_validate(
            _add_activity_item(db_path, activity_id, body, database.add_role)
        )

    @app.post(
        "/api/activities/{activity_id}/members",
        status_code=201,
        response_model=MemberResponse,
        responses=error_responses,
    )
    async def add_member(activity_id: str, body: Any = Body(default=None)) -> MemberResponse:
        body = _read_json_object(body)
        try:
            return MemberResponse.model_validate(
                database.add_member(
                    db_path,
                    _parse_id(activity_id),
                    _read_text(body, "name"),
                    _read_email(body, "email"),
                )
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

    @app.get(
        "/api/activities/{activity_id}/assignments",
        response_model=AssignmentsResponse,
        responses=error_responses,
    )
    async def list_assignments(activity_id: str) -> AssignmentsResponse:
        try:
            assignments = database.list_assignments(db_path, _parse_id(activity_id))
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return AssignmentsResponse(assignments=assignments)

    @app.get(
        "/api/activities/{activity_id}/assignments/dates/{assigned_on}",
        response_model=AssignmentsResponse,
        responses=error_responses,
    )
    async def list_assignments_on(
        activity_id: str, assigned_on: str
    ) -> AssignmentsResponse:
        try:
            assignments = database.list_assignments_on(
                db_path,
                _parse_id(activity_id),
                _clean_date(assigned_on, "assigned_on"),
            )
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return AssignmentsResponse(assignments=assignments)

    @app.post(
        "/api/activities/{activity_id}/assignments",
        status_code=201,
        response_model=AssignmentResponse,
        responses=error_responses,
    )
    async def add_assignment(
        activity_id: str, body: Any = Body(default=None)
    ) -> AssignmentResponse:
        body = _read_json_object(body)
        try:
            assignment = database.add_assignment(
                db_path,
                _parse_id(activity_id),
                _read_body_id(body, "role_id"),
                _read_body_id(body, "member_id"),
                _read_optional_date(body, "assigned_on"),
            )
            events.publish_assignments_changed(1)
            return AssignmentResponse.model_validate(assignment)
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
            events.publish_assignments_changed(1)
        except database.NotFoundError as error:
            raise _api_error(404, str(error)) from error
        return Response(status_code=204)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def api_not_found(path: str) -> None:
        raise _api_error(404, "対象が見つかりませんでした。")

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


async def stream_events(request: Request):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop_event = threading.Event()

    def subscribe() -> None:
        for message in events.subscribe_events(stop_event.is_set):
            loop.call_soon_threadsafe(queue.put_nowait, message)
        loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=subscribe, daemon=True)
    thread.start()

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if message is None:
                break
            yield f"data: {message}\n\n"
    finally:
        stop_event.set()


def _read_json_object(parsed: Any) -> dict[str, Any]:
    if parsed is None:
        return {}

    if not isinstance(parsed, dict):
        raise _api_error(400, "リクエストの形式が正しくありません。")
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
        raise _api_error(400, "IDが正しくありません。") from error


def _read_body_id(body: dict[str, Any], key: str) -> int:
    if key not in body:
        raise _api_error(400, f"{_field_label(key)}は必須です。")
    return _parse_id(str(body[key]))


def _read_text(body: dict[str, Any], key: str) -> str:
    return _clean_text(body.get(key, ""), key)


def _read_email(body: dict[str, Any], key: str) -> str:
    cleaned = _clean_text(body.get(key, ""), key).lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise _api_error(400, f"{_field_label(key)}は正しい形式で入力してください。")
    return cleaned


def _clean_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise _api_error(400, f"{_field_label(field_name)}は文字列で入力してください。")

    if any(unicodedata.category(character).startswith("C") for character in value):
        raise _api_error(400, f"{_field_label(field_name)}に使用できない文字が含まれています。")

    cleaned = value.strip()
    if not cleaned:
        raise _api_error(400, f"{_field_label(field_name)}は必須です。")
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise _api_error(
            400, f"{_field_label(field_name)}は{MAX_TEXT_LENGTH}文字以内で入力してください。"
        )
    return cleaned


def _read_optional_date(body: dict[str, Any], key: str) -> str | None:
    if key not in body or body[key] is None:
        return None
    if not isinstance(body[key], str):
        raise _api_error(400, f"{_field_label(key)}は文字列で入力してください。")
    return _clean_date(body[key], key)


def _clean_date(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise _api_error(400, f"{_field_label(field_name)}は必須です。")
    try:
        date.fromisoformat(cleaned)
    except ValueError as error:
        raise _api_error(
            400, f"{_field_label(field_name)}はYYYY-MM-DD形式の正しい日付を入力してください。"
        ) from error
    return cleaned


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": message})


def _field_label(field_name: str) -> str:
    labels = {
        "assigned_on": "担当日",
        "email": "メールアドレス",
        "member_id": "メンバーID",
        "name": "名前",
        "role_id": "役割ID",
    }
    return labels.get(field_name, field_name)


def run(
    host: str = "127.0.0.1",
    port: int = 8000,
    db_path: Path = DEFAULT_DB_PATH,
    pid_path: Path = DEFAULT_PID_PATH,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    write_pid_file(pid_path)
    print(f"ttk is running at http://{host}:{port}")
    uvicorn.run(create_app(db_path), host=host, port=port)


def write_pid_file(pid_path: Path) -> None:
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")

    def remove_pid_file() -> None:
        try:
            if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pid_path.unlink()
        except OSError:
            pass

    atexit.register(remove_pid_file)


if __name__ == "__main__":
    run()
