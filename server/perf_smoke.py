from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import events, rotation
from .config import DEFAULT_DB_PATH


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass
class ActivityPlan:
    index: int
    activity: dict[str, Any]
    member_count: int
    role_count: int
    requested_role_count: int
    members: list[dict[str, Any]] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    skips: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)


@dataclass
class Metrics:
    activities_created: int = 0
    setup_completed: int = 0
    members_created: int = 0
    roles_created: int = 0
    role_counts_capped: int = 0
    initial_assignments_created: int = 0
    rotations: int = 0
    rotated_assignments: int = 0
    assignment_reads: int = 0
    skip_toggles: int = 0
    skips_created: int = 0
    skips_deleted: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Docker環境でAPI作成・ローテーション・担当取得の簡易性能試験を行います。"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"APIのURL。デフォルトは {DEFAULT_BASE_URL}",
    )
    parser.add_argument("--activities", type=positive_int, default=1000)
    parser.add_argument("--min-members", type=positive_int, default=1)
    parser.add_argument("--max-members", type=positive_int, default=10)
    parser.add_argument("--min-roles", type=positive_int, default=1)
    parser.add_argument("--max-roles", type=positive_int, default=10)
    parser.add_argument("--rotations", type=non_negative_int, default=100)
    parser.add_argument("--reads", type=non_negative_int, default=1000)
    parser.add_argument("--skips", type=non_negative_int, default=100)
    parser.add_argument("--random-seed", type=int, default=1)
    parser.add_argument(
        "--base-date",
        default=date.today().isoformat(),
        type=valid_date,
        help="初期担当日のYYYY-MM-DD。デフォルトは実行日です。",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"API起動待ちの秒数。デフォルトは {DEFAULT_TIMEOUT_SECONDS} 秒です。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_ranges(args)

    rng = random.Random(args.random_seed)
    base_url = args.base_url.rstrip("/")
    base_date = date.fromisoformat(args.base_date)
    db_path = Path(os.environ.get("TTK_DB_PATH", DEFAULT_DB_PATH))

    print(
        "Performance smoke started: "
        f"activities={args.activities}, "
        f"members={args.min_members}-{args.max_members}, "
        f"roles={args.min_roles}-{args.max_roles}, "
        f"rotations={args.rotations}, "
        f"reads={args.reads}, "
        f"skips={args.skips}, "
        f"base_date={args.base_date}, "
        f"random_seed={args.random_seed}",
        flush=True,
    )

    total_started = time.perf_counter()
    wait_for_api(base_url, args.timeout)

    create_started = time.perf_counter()
    plans = create_activities(base_url, args.activities, rng, args)
    create_seconds = time.perf_counter() - create_started

    mixed_started = time.perf_counter()
    metrics = run_mixed_operations(base_url, plans, base_date, db_path, rng, args)
    mixed_seconds = time.perf_counter() - mixed_started
    total_seconds = time.perf_counter() - total_started

    metrics.activities_created = len(plans)
    print_summary(metrics, create_seconds, mixed_seconds, total_seconds)


def create_activities(
    base_url: str, count: int, rng: random.Random, args: argparse.Namespace
) -> list[ActivityPlan]:
    plans = []

    for index in range(1, count + 1):
        activity = request_json(
            "POST",
            f"{base_url}/api/activities",
            {"name": f"性能試験アクティビティ{index}"},
            expected_status=201,
        )
        member_count = rng.randint(args.min_members, args.max_members)
        requested_role_count = rng.randint(args.min_roles, args.max_roles)
        role_count = min(requested_role_count, member_count)
        plans.append(
            ActivityPlan(
                index=index,
                activity=activity,
                member_count=member_count,
                role_count=role_count,
                requested_role_count=requested_role_count,
            )
        )
        print_progress("activities", index, count)

    return plans


def run_mixed_operations(
    base_url: str,
    plans: list[ActivityPlan],
    base_date: date,
    db_path: Path,
    rng: random.Random,
    args: argparse.Namespace,
) -> Metrics:
    metrics = Metrics()
    rotation_dates = [
        (base_date + timedelta(days=offset)).isoformat()
        for offset in range(1, args.rotations + 1)
    ]

    operations: list[tuple[str, int | str]] = [
        ("setup", index) for index in range(len(plans))
    ]
    operations.extend(("rotate", assigned_on) for assigned_on in rotation_dates)
    operations.extend(("read", rng.randrange(len(plans))) for _ in range(args.reads))
    operations.extend(("skip", rng.randrange(len(plans))) for _ in range(args.skips))
    rng.shuffle(operations)
    total_operations = len(operations)

    done = 0
    deferred_skips = 0
    while operations:
        operation, value = operations.pop(0)
        if operation == "setup":
            setup_activity(base_url, plans[int(value)], base_date.isoformat(), metrics)
        elif operation == "rotate":
            rotate_assignments(db_path, str(value), metrics)
        elif operation == "read":
            read_assignments(base_url, plans[int(value)], metrics)
        elif operation == "skip":
            plan = plans[int(value)]
            if not plan.members or not plan.roles:
                operations.append((operation, value))
                deferred_skips += 1
                if deferred_skips > len(plans) + args.skips:
                    raise RuntimeError("スキップ操作を実行できる活動がありません。")
                continue
            toggle_skip(base_url, plan, rng, metrics)
            deferred_skips = 0
        else:
            raise RuntimeError(f"unknown operation: {operation}")
        done += 1
        print_progress("mixed operations", done, total_operations)

    return metrics


def setup_activity(
    base_url: str, plan: ActivityPlan, assigned_on: str, metrics: Metrics
) -> None:
    activity_id = plan.activity["id"]

    for member_index in range(1, plan.member_count + 1):
        member = request_json(
            "POST",
            f"{base_url}/api/activities/{activity_id}/members",
            {
                "name": f"会員{plan.index}-{member_index}",
                "email": f"perf-{plan.index}-{member_index}@example.com",
            },
            expected_status=201,
        )
        plan.members.append(member)
        metrics.members_created += 1

    if plan.role_count < plan.requested_role_count:
        metrics.role_counts_capped += 1

    for role_index in range(1, plan.role_count + 1):
        role = request_json(
            "POST",
            f"{base_url}/api/activities/{activity_id}/roles",
            {"name": f"役割{plan.index}-{role_index}"},
            expected_status=201,
        )
        plan.roles.append(role)
        metrics.roles_created += 1

    for role_index, role in enumerate(plan.roles):
        request_json(
            "POST",
            f"{base_url}/api/activities/{activity_id}/assignments",
            {
                "role_id": role["id"],
                "member_id": plan.members[role_index % len(plan.members)]["id"],
                "assigned_on": assigned_on,
            },
            expected_status=201,
        )
        metrics.initial_assignments_created += 1

    metrics.setup_completed += 1


def rotate_assignments(db_path: Path, assigned_on: str, metrics: Metrics) -> None:
    created = rotation.rotate_once(db_path, assigned_on)
    if created:
        events.publish_assignments_changed(
            len(created),
            assigned_on=assigned_on,
            activity_ids=sorted({item["activity_id"] for item in created}),
        )
    metrics.rotations += 1
    metrics.rotated_assignments += len(created)


def read_assignments(base_url: str, plan: ActivityPlan, metrics: Metrics) -> None:
    request_json(
        "GET",
        f"{base_url}/api/activities/{plan.activity['id']}/assignments",
        expected_status=200,
    )
    metrics.assignment_reads += 1


def toggle_skip(
    base_url: str, plan: ActivityPlan, rng: random.Random, metrics: Metrics
) -> None:
    total_pairs = len(plan.roles) * len(plan.members)
    should_delete = plan.skips and (
        rng.random() < 0.5 or len(plan.skips) >= total_pairs
    )

    if should_delete:
        role_id, member_id = rng.choice(list(plan.skips))
        response = request_json(
            "DELETE",
            skip_path(base_url, plan, role_id, member_id),
            expected_status={204, 404},
        )
        plan.skips.pop((role_id, member_id), None)
        if response["_status"] == 204:
            metrics.skips_deleted += 1
    else:
        role = rng.choice(plan.roles)
        member = rng.choice(plan.members)
        key = (role["id"], member["id"])
        skip = request_json(
            "POST",
            skip_path(base_url, plan, role["id"]),
            {"member_id": member["id"]},
            expected_status=201,
        )
        plan.skips[key] = skip
        metrics.skips_created += 1

    metrics.skip_toggles += 1


def skip_path(
    base_url: str, plan: ActivityPlan, role_id: int, member_id: int | None = None
) -> str:
    path = f"{base_url}/api/activities/{plan.activity['id']}/roles/{role_id}/skips"
    if member_id is not None:
        path = f"{path}/{member_id}"
    return path


def wait_for_api(base_url: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            request_json("GET", f"{base_url}/api/activities", expected_status=200)
            return
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1)

    raise SystemExit(f"APIに接続できませんでした: {last_error}")


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    expected_status: int | set[int] = 200,
) -> dict[str, Any]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            expected_statuses = normalize_expected_status(expected_status)
            if response.status not in expected_statuses:
                raise RuntimeError(f"{method} {url} returned HTTP {response.status}")
            if not raw:
                return {"_status": response.status}
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                parsed.setdefault("_status", response.status)
            return parsed
    except urllib.error.HTTPError as error:
        expected_statuses = normalize_expected_status(expected_status)
        if error.code in expected_statuses:
            error.read()
            return {"_status": error.code}
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {url} returned HTTP {error.code}: {detail}"
        ) from error


def print_progress(label: str, done: int, total: int) -> None:
    if total <= 10 or done == total or done % max(1, total // 10) == 0:
        print(f"{label}: {done}/{total}", flush=True)


def print_summary(
    metrics: Metrics, create_seconds: float, mixed_seconds: float, total_seconds: float
) -> None:
    print("Performance smoke OK", flush=True)
    print(f"activities_created: {metrics.activities_created}", flush=True)
    print(f"setup_completed: {metrics.setup_completed}", flush=True)
    print(f"members_created: {metrics.members_created}", flush=True)
    print(f"roles_created: {metrics.roles_created}", flush=True)
    print(f"role_counts_capped: {metrics.role_counts_capped}", flush=True)
    print(
        f"initial_assignments_created: {metrics.initial_assignments_created}",
        flush=True,
    )
    print(f"rotations: {metrics.rotations}", flush=True)
    print(f"rotated_assignments: {metrics.rotated_assignments}", flush=True)
    print(f"assignment_reads: {metrics.assignment_reads}", flush=True)
    print(f"skip_toggles: {metrics.skip_toggles}", flush=True)
    print(f"skips_created: {metrics.skips_created}", flush=True)
    print(f"skips_deleted: {metrics.skips_deleted}", flush=True)
    print(f"activity_create_seconds: {create_seconds:.2f}", flush=True)
    print(f"mixed_operations_seconds: {mixed_seconds:.2f}", flush=True)
    print(f"total_seconds: {total_seconds:.2f}", flush=True)


def validate_ranges(args: argparse.Namespace) -> None:
    if args.min_members > args.max_members:
        raise SystemExit("min-members は max-members 以下にしてください。")
    if args.min_roles > args.max_roles:
        raise SystemExit("min-roles は max-roles 以下にしてください。")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("0以上の整数を指定してください。")
    return parsed


def valid_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("YYYY-MM-DD形式の正しい日付を指定してください。") from error
    return value


def normalize_expected_status(expected_status: int | set[int]) -> set[int]:
    if isinstance(expected_status, int):
        return {expected_status}
    return expected_status


if __name__ == "__main__":
    main()
