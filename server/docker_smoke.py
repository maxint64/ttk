from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Docker環境のseed/rotate/API応答を確認します。"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"確認対象のURL。デフォルトは {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="ローテーション結果を確認する日付。YYYY-MM-DD形式で指定します。",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"API起動待ちの秒数。デフォルトは {DEFAULT_TIMEOUT_SECONDS} 秒です。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = wait_for_activities(args.base_url, args.timeout)
    activities = validate_activities(data, args.date)
    print(
        "Docker smoke OK: "
        f"activities={len(activities)}, "
        f"rotated_assignments={count_assignments_on(activities, args.date)}"
    )


def wait_for_activities(base_url: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            return fetch_json(f"{base_url.rstrip('/')}/api/activities")
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1)

    raise SystemExit(f"Docker APIに接続できませんでした: {last_error}")


def fetch_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}") from error


def validate_activities(data: dict[str, Any], rotated_on: str) -> list[dict[str, Any]]:
    activities = data.get("activities")
    if not isinstance(activities, list):
        raise SystemExit("APIレスポンスにactivities配列がありません。")

    if len(activities) != 2:
        raise SystemExit(f"seed後のアクティビティ件数が不正です: {len(activities)}")

    rotated_assignments = count_assignments_on(activities, rotated_on)
    if rotated_assignments != 4:
        raise SystemExit(
            f"{rotated_on} のローテーション結果が不正です: {rotated_assignments}"
        )

    return activities


def count_assignments_on(activities: list[dict[str, Any]], assigned_on: str) -> int:
    return sum(
        1
        for activity in activities
        for assignment in activity.get("assignments", [])
        if assignment.get("assigned_on") == assigned_on
    )


if __name__ == "__main__":
    main()
