from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from server.config import DEFAULT_PID_PATH, PROJECT_ROOT


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
            remove_pid_file(DEFAULT_PID_PATH)
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
    remove_pid_file(DEFAULT_PID_PATH)
    if killed:
        print(f"Force-stopped {killed} process(es) that did not exit after SIGTERM.")


def find_server_processes() -> list[int]:
    current_pid = os.getpid()
    targets = set(read_pid_file_targets(DEFAULT_PID_PATH))
    proc = Path("/proc")
    if not proc.exists():
        return sorted(pid for pid in targets if pid != current_pid)

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

        targets.add(pid)

    return sorted(pid for pid in targets if pid != current_pid)


def read_pid_file_targets(pid_path: Path) -> list[int]:
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
    except OSError:
        return []

    try:
        pid = int(raw)
    except ValueError:
        return []

    if pid <= 0 or not process_exists(pid):
        remove_pid_file(pid_path)
        return []

    if not looks_like_server_process(pid):
        remove_pid_file(pid_path)
        return []

    return [pid]


def read_cmdline(proc_entry: Path) -> list[str]:
    try:
        raw = (proc_entry / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="ignore") for part in raw.split(b"\0") if part]


def cwd_is_project(proc_entry: Path) -> bool:
    try:
        cwd = normalized_path((proc_entry / "cwd").resolve())
    except OSError:
        return False

    try:
        cwd.relative_to(normalized_path(PROJECT_ROOT))
    except ValueError:
        return False
    return True


def looks_like_server_process(pid: int) -> bool:
    proc_entry = Path("/proc") / str(pid)
    if not proc_entry.exists():
        return False
    cmdline = read_cmdline(proc_entry)
    return "-m" in cmdline and "server.run" in cmdline and cwd_is_project(proc_entry)


def normalized_path(path: Path) -> Path:
    return Path(str(path).lower())


def remove_pid_file(pid_path: Path) -> None:
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass


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
