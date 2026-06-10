"""阶段3: 点击执行。

支持失焦点击: 点击后把前台焦点归还给用户原窗口, 并可还原鼠标位置,
最小化对用户当前操作的打扰。
"""
from __future__ import annotations

import time

import pyautogui

from .config import ClickConfig

pyautogui.FAILSAFE = False

try:
    import win32gui

    _HAS_WIN32 = True
except ImportError:  # 非 Windows 或未装 pywin32 时降级
    _HAS_WIN32 = False


class Clicker:
    def __init__(self, cfg: ClickConfig) -> None:
        self.cfg = cfg

    def _foreground_window(self):
        if _HAS_WIN32:
            try:
                return win32gui.GetForegroundWindow()
            except Exception:
                return None
        return None

    def _restore_window(self, hwnd) -> None:
        if _HAS_WIN32 and hwnd:
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def click(self, x: int, y: int) -> None:
        prev_hwnd = self._foreground_window() if self.cfg.restore_focus else None
        prev_pos = pyautogui.position() if self.cfg.restore_mouse else None

        pyautogui.click(x, y)

        if prev_pos is not None:
            try:
                pyautogui.moveTo(prev_pos.x, prev_pos.y)
            except Exception:
                pass
        if prev_hwnd is not None:
            # 略等渲染, 再把焦点还给用户原窗口
            time.sleep(0.05)
            self._restore_window(prev_hwnd)
