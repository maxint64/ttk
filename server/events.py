from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlparse


DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_CHANNEL = "ttk:events"


@dataclass(frozen=True)
class RedisSettings:
    host: str
    port: int
    db: int
    channel: str


def publish_assignments_changed(count: int) -> None:
    publish_event({"type": "assignments_changed", "count": count})


def publish_event(payload: dict[str, object]) -> None:
    settings = redis_settings()
    try:
        with socket.create_connection((settings.host, settings.port), timeout=1) as sock:
            send_command(sock, "SELECT", str(settings.db))
            read_response(sock)
            send_command(sock, "PUBLISH", settings.channel, json.dumps(payload))
            read_response(sock)
    except OSError:
        return


def subscribe_events(stop_requested) -> Iterator[str]:
    settings = redis_settings()
    while not stop_requested():
        try:
            with socket.create_connection((settings.host, settings.port), timeout=2) as sock:
                sock.settimeout(1)
                send_command(sock, "SELECT", str(settings.db))
                read_response(sock)
                send_command(sock, "SUBSCRIBE", settings.channel)
                read_response(sock)

                while not stop_requested():
                    try:
                        message = read_response(sock)
                    except TimeoutError:
                        continue
                    if (
                        isinstance(message, list)
                        and len(message) == 3
                        and message[0] == "message"
                    ):
                        yield str(message[2])
        except OSError:
            if not stop_requested():
                time.sleep(1)


def redis_settings() -> RedisSettings:
    parsed = urlparse(os.environ.get("TTK_REDIS_URL", DEFAULT_REDIS_URL))
    db = 0
    if parsed.path and parsed.path != "/":
        db = int(parsed.path.lstrip("/"))
    return RedisSettings(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 6379,
        db=db,
        channel=os.environ.get("TTK_EVENTS_CHANNEL", DEFAULT_CHANNEL),
    )


def send_command(sock: socket.socket, *parts: str) -> None:
    encoded = [part.encode("utf-8") for part in parts]
    command = [f"*{len(encoded)}\r\n".encode("ascii")]
    for part in encoded:
        command.append(f"${len(part)}\r\n".encode("ascii"))
        command.append(part)
        command.append(b"\r\n")
    sock.sendall(b"".join(command))


def read_response(sock: socket.socket):
    prefix = read_exact(sock, 1)
    if prefix == b"+":
        return read_line(sock)
    if prefix == b":":
        return int(read_line(sock))
    if prefix == b"$":
        length = int(read_line(sock))
        if length == -1:
            return None
        data = read_exact(sock, length)
        read_exact(sock, 2)
        return data.decode("utf-8")
    if prefix == b"*":
        length = int(read_line(sock))
        return [read_response(sock) for _ in range(length)]
    if prefix == b"-":
        raise OSError(read_line(sock))
    raise OSError("unexpected Redis response")


def read_line(sock: socket.socket) -> str:
    chunks = []
    while True:
        byte = read_exact(sock, 1)
        if byte == b"\r":
            read_exact(sock, 1)
            return b"".join(chunks).decode("utf-8")
        chunks.append(byte)


def read_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise OSError("Redis connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
