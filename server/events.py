from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator

import redis
from redis.exceptions import RedisError


DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"
DEFAULT_CHANNEL = "ttk:events"
logger = logging.getLogger(__name__)


def publish_assignments_changed(
    count: int,
    assigned_on: str | None = None,
    activity_id: int | None = None,
    activity_ids: list[int] | None = None,
) -> None:
    payload: dict[str, object] = {"type": "assignments_changed", "count": count}
    if assigned_on is not None:
        payload["assigned_on"] = assigned_on
    if activity_id is not None:
        payload["activity_id"] = activity_id
    if activity_ids is not None:
        payload["activity_ids"] = activity_ids
    publish_event(payload)


def publish_data_changed(kind: str, count: int = 1, **extra: object) -> None:
    publish_event({"type": kind, "count": count, **extra})


def publish_event(payload: dict[str, object]) -> None:
    try:
        client().publish(channel_name(), json.dumps(payload))
    except RedisError as error:
        logger.exception("Failed to publish event to Redis: %s", error)
        return


def subscribe_events(stop_requested) -> Iterator[str]:
    was_disconnected = False
    while not stop_requested():
        try:
            pubsub = client().pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel_name())
            if was_disconnected:
                logger.info("Redis event subscription reconnected.")
                was_disconnected = False
            try:
                while not stop_requested():
                    message = pubsub.get_message(timeout=1)
                    if message and message["type"] == "message":
                        yield decode_message(message["data"])
            finally:
                pubsub.close()
        except RedisError as error:
            if not was_disconnected:
                logger.exception("Failed to subscribe to Redis events: %s", error)
                was_disconnected = True
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
