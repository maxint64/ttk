from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from server.config import PROJECT_ROOT


def main() -> None:
    targets = find_server_processes()
    if not targets:
        print("No local ttk development server is running.")
        return

    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        remaining = [pid for pid in targets if process_exists(pid)]
        if not remaining:
            print(f"Stopped {len(targets)} local ttk development server process(es).")
            return
        time.sleep(0.1)

    killed = 0
    for pid in targets:
        if not process_exists(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            killed += 1
        except ProcessLookupError:
            pass

    print(f"Stopped {len(targets)} local ttk development server process(es).")
    if killed:
        print(f"Force-stopped {killed} process(es) that did not exit after SIGTERM.")


def find_server_processes() -> list[int]:
    current_pid = os.getpid()
    targets: list[int] = []
    proc = Path("/proc")
    if not proc.exists():
        return targets

    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)
        if pid == current_pid:
            continue

        cmdline = read_cmdline(entry)
        if "-m" not in cmdline or "server.run" not in cmdline:
            continue
        if not cwd_is_project(entry):
            continue

        targets.append(pid)

    return targets


def read_cmdline(proc_entry: Path) -> list[str]:
    try:
        raw = (proc_entry / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="ignore") for part in raw.split(b"\0") if part]


def cwd_is_project(proc_entry: Path) -> bool:
    try:
        cwd = (proc_entry / "cwd").resolve()
    except OSError:
        return False

    try:
        cwd.relative_to(PROJECT_ROOT)
    except ValueError:
        return False
    return True


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


if __name__ == "__main__":
    main()
