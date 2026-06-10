"""桌面托盘小助手: 一键启停 Cursor 自动确认。

双击桌面快捷方式或运行 launch.bat 后, 在任务栏右下角托盘区显示图标:
  - 绿色 = 自动点击运行中
  - 灰色 = 已停止
右键菜单可 启动 / 停止 / 打开日志 / 退出托盘程序。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

# 允许直接运行
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.paths import project_root
    from src.process_manager import is_worker_running, start_worker, stop_worker
else:
    from .paths import project_root
    from .process_manager import is_worker_running, start_worker, stop_worker

import pystray

if __package__ in (None, ""):
    from src.icon_assets import make_icon
else:
    from .icon_assets import make_icon

TRAY_LOCK = os.path.join(project_root(), "tray.lock")
POLL_SECONDS = 2.0


def _pid_alive(pid: int) -> bool:
    try:
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def acquire_tray_lock() -> bool:
    if os.path.exists(TRAY_LOCK):
        try:
            with open(TRAY_LOCK, "r", encoding="ascii") as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return False
        except (ValueError, OSError):
            pass
    with open(TRAY_LOCK, "w", encoding="ascii") as f:
        f.write(str(os.getpid()))
    return True


def release_tray_lock() -> None:
    try:
        if os.path.exists(TRAY_LOCK):
            os.remove(TRAY_LOCK)
    except OSError:
        pass


class TrayController:
    def __init__(self) -> None:
        self._running = False
        self._icon: pystray.Icon | None = None
        self._stop_poll = threading.Event()

    def _title(self) -> str:
        return "Cursor 自动确认 - 运行中" if self._running else "Cursor 自动确认 - 已停止"

    def _rebuild_menu(self) -> pystray.Menu:
        if self._running:
            start_item = pystray.MenuItem("已在运行", None, enabled=False)
            stop_item = pystray.MenuItem("停止自动点击", self.on_stop)
        else:
            start_item = pystray.MenuItem("启动自动点击", self.on_start)
            stop_item = pystray.MenuItem("已停止", None, enabled=False)
        return pystray.Menu(
            start_item,
            stop_item,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开日志", self.on_open_log),
            pystray.MenuItem("打开项目文件夹", self.on_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出托盘程序", self.on_quit),
        )

    def _refresh(self) -> None:
        if not self._icon:
            return
        self._running = is_worker_running()
        self._icon.icon = make_icon(self._running)
        self._icon.title = self._title()
        self._icon.menu = self._rebuild_menu()

    def _poll_loop(self) -> None:
        while not self._stop_poll.is_set():
            try:
                self._refresh()
            except Exception:
                pass
            self._stop_poll.wait(POLL_SECONDS)

    def on_start(self, _icon=None, _item=None) -> None:
        try:
            started = start_worker()
            if started:
                time.sleep(0.8)
        except Exception as e:
            self._notify(f"启动失败: {e}")
        self._refresh()

    def on_stop(self, _icon=None, _item=None) -> None:
        stop_worker()
        time.sleep(0.3)
        self._refresh()

    def on_open_log(self, _icon=None, _item=None) -> None:
        log_path = os.path.join(project_root(), "logs", "autopilot.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            open(log_path, "a", encoding="utf-8").close()
        os.startfile(log_path)

    def on_open_folder(self, _icon=None, _item=None) -> None:
        os.startfile(project_root())

    def on_quit(self, _icon=None, _item=None) -> None:
        self._stop_poll.set()
        if self._icon:
            self._icon.stop()

    def _notify(self, msg: str) -> None:
        if self._icon:
            try:
                self._icon.notify(msg, "Cursor 自动确认")
            except Exception:
                pass

    def run(self) -> None:
        self._running = is_worker_running()
        self._icon = pystray.Icon(
            "cursor_autopilot",
            make_icon(self._running),
            self._title(),
            self._rebuild_menu(),
        )
        threading.Thread(target=self._poll_loop, daemon=True).start()
        try:
            self._icon.run()
        finally:
            self._stop_poll.set()
            release_tray_lock()


def main() -> int:
    if not acquire_tray_lock():
        # 已有托盘实例, 尝试弹出提示后退出
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                "托盘程序已在运行。\n请在任务栏右下角找到绿色/灰色圆形图标。",
                "Cursor 自动确认",
                0x40,
            )
        except Exception:
            pass
        return 0
    try:
        TrayController().run()
    finally:
        release_tray_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
