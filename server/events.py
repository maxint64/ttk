from __future__ import annotations

import json
import os
import time
from typing import Iterator

import redis
from redis.exceptions import RedisError


DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_CHANNEL = "ttk:events"


def publish_assignments_changed(count: int) -> None:
    publish_event({"type": "assignments_changed", "count": count})


def publish_event(payload: dict[str, object]) -> None:
    try:
        client().publish(channel_name(), json.dumps(payload))
    except RedisError:
        return


def subscribe_events(stop_requested) -> Iterator[str]:
    while not stop_requested():
        try:
            pubsub = client().pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel_name())
            try:
                while not stop_requested():
                    message = pubsub.get_message(timeout=1)
                    if message and message["type"] == "message":
                        yield decode_message(message["data"])
            finally:
                pubsub.close()
        except RedisError:
            if not stop_requested():
                time.sleep(1)


def client() -> redis.Redis:
    return redis.Redis.from_url(
        os.environ.get("TTK_REDIS_URL", DEFAULT_REDIS_URL),
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def channel_name() -> str:
    return os.environ.get("TTK_EVENTS_CHANNEL", DEFAULT_CHANNEL)


def decode_message(data) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)
