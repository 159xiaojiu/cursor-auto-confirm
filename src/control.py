"""阶段5: 控制层。全局热键启停/退出 + 用户活动检测。"""
from __future__ import annotations

import threading
import time

import pyautogui

from .config import ClickConfig, HotkeyConfig

try:
    import keyboard

    _HAS_KEYBOARD = True
except Exception:
    _HAS_KEYBOARD = False


class UserActivityMonitor:
    """轻量用户活动检测: 轮询鼠标位置变化, 监听键盘事件。
    用户近期有活动时, 自动点击应让位暂停。"""

    def __init__(self, pause_seconds: float = 2.0) -> None:
        self.pause_seconds = pause_seconds
        self._last_active = 0.0
        self._last_mouse = pyautogui.position()
        if _HAS_KEYBOARD:
            keyboard.on_press(lambda _e: self._touch())

    def _touch(self) -> None:
        self._last_active = time.monotonic()

    def poll_mouse(self) -> None:
        pos = pyautogui.position()
        if pos != self._last_mouse:
            self._last_mouse = pos
            self._touch()

    def is_user_active(self) -> bool:
        self.poll_mouse()
        return (time.monotonic() - self._last_active) < self.pause_seconds


class HotkeyController:
    def __init__(self, cfg: HotkeyConfig) -> None:
        self.cfg = cfg
        self.enabled = True            # 自动点击是否开启
        self._quit = threading.Event()
        self._registered = False

    def register(self) -> None:
        if not _HAS_KEYBOARD or self._registered:
            return
        try:
            keyboard.add_hotkey(self.cfg.toggle, self.toggle)
            keyboard.add_hotkey(self.cfg.quit, self.request_quit)
            self._registered = True
        except Exception:
            pass

    def toggle(self) -> None:
        self.enabled = not self.enabled
        state = "运行中" if self.enabled else "已暂停"
        print(f"[热键] 自动点击 -> {state}")

    def request_quit(self) -> None:
        print("[热键] 收到退出指令")
        self._quit.set()

    def should_quit(self) -> bool:
        return self._quit.is_set()
