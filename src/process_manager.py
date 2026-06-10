"""后台工作进程的启停管理(供托盘 App / 脚本共用)。"""
from __future__ import annotations

import os
import subprocess
import sys

from .paths import is_frozen, project_root, worker_command


def lock_path() -> str:
    return os.path.join(project_root(), "autopilot.lock")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def worker_pid() -> int | None:
    path = lock_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="ascii") as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return None
    return pid if _pid_alive(pid) else None


def is_worker_running() -> bool:
    return worker_pid() is not None


def _stop_ps_filter() -> str:
    if is_frozen():
        exe = os.path.basename(sys.executable)
        return (
            f"($_.CommandLine -like '*{exe}*--worker*')"
        )
    return "($_.CommandLine -like '*src.main*')"


def stop_worker() -> None:
    """停止所有工作进程并清理锁文件。"""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe' "
        "-or $_.Name -like 'CursorAutoConfirm*') "
        f"-and {_stop_ps_filter()} "
        "} | ForEach-Object { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        cwd=project_root(),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    try:
        if os.path.exists(lock_path()):
            os.remove(lock_path())
    except OSError:
        pass


def start_worker() -> bool:
    """启动后台工作进程。已在运行则返回 False。"""
    if is_worker_running():
        return False
    cmd = worker_command()
    if not os.path.isfile(cmd[0]) and not is_frozen():
        raise FileNotFoundError(f"未找到 Python: {cmd[0]}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        cmd,
        cwd=project_root(),
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return True
