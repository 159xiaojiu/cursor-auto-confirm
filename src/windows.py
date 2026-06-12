"""多 Cursor 窗口支持。

枚举 Cursor 主窗口(含 Home / Cursor Agents / 项目窗口),
离屏抓取 + 后台窗口短暂刷新, 支持多窗口同时照看。
"""
from __future__ import annotations

import os
import time
from ctypes import byref, c_uint, create_unicode_buffer, windll
from dataclasses import dataclass

import numpy as np
import win32gui
import win32process
import win32ui

PW_RENDERFULLCONTENT = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9

user32 = windll.user32
kernel32 = windll.kernel32

# 排除的小窗口/系统辅助窗口
_SKIP_TITLES = frozenset({
    "CandidateWindow", "Mode Indicator", "Default IME", "MSCTFIME UI",
    "GDI+ Window (Cursor.exe)",
})


@dataclass
class CursorWindow:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    minimized: bool


def enable_dpi_awareness() -> None:
    try:
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _proc_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        buf = create_unicode_buffer(1024)
        size = c_uint(1024)
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, byref(size))
        kernel32.CloseHandle(h)
        return os.path.basename(buf.value) if ok else ""
    except Exception:
        return ""


def _is_cursor_main_window(title: str) -> bool:
    t = (title or "").strip()
    if not t or t in _SKIP_TITLES:
        return False
    if t.startswith("Default IME") or t.startswith("MSCTF"):
        return False
    # Home 页: 标题就是 "Cursor"
    if t == "Cursor":
        return True
    # Agent / Home 侧边栏聊天: "Cursor Agents"
    if t == "Cursor Agents":
        return True
    # 项目窗口: "xxx - Cursor"
    if t.endswith(" - Cursor"):
        return True
    return False


def list_cursor_windows(min_w: int = 400, min_h: int = 280) -> list[CursorWindow]:
    found: list[CursorWindow] = []

    def cb(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return
        if not win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not _is_cursor_main_window(title):
            return
        if _proc_name(hwnd).lower() != "cursor.exe":
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top
        if w < min_w or h < min_h:
            return
        found.append(
            CursorWindow(
                hwnd=hwnd, title=title, left=left, top=top,
                width=w, height=h, minimized=bool(win32gui.IsIconic(hwnd)),
            )
        )

    win32gui.EnumWindows(cb, None)
    return found


def _is_good_capture(img: np.ndarray | None) -> bool:
    if img is None or img.size == 0:
        return False
    gray = img.mean(axis=2)
    mean, std = float(gray.mean()), float(gray.std())
    # Electron 后台 PrintWindow 常返回近乎全黑/全灰的空图
    return mean > 18 and std > 10


def _capture_printwindow(hwnd: int) -> np.ndarray | None:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    try:
        ok = user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        if not ok:
            ok = user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
        if not ok:
            return None
        info = bmp.GetInfo()
        bits = bmp.GetBitmapBits(True)
        img = np.frombuffer(bits, dtype=np.uint8).reshape(
            (info["bmHeight"], info["bmWidth"], 4)
        )
        return img[:, :, :3].copy()
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


_last_foreground_refresh: dict[int, float] = {}
_last_composer_scroll: dict[int, float] = {}
_FOREGROUND_REFRESH_COOLDOWN = 2.0
_COMPOSER_SCROLL_COOLDOWN = 2.5


def is_composer_window(title: str) -> bool:
    """带 Agent/Composer 聊天区的窗口(需滚到底才能看到最新确认按钮)。"""
    return title == "Cursor Agents" or title.endswith(" - Cursor")


def _composer_click_point(win: CursorWindow) -> tuple[int, int]:
    """Composer 聊天区内的点击坐标(用于聚焦并滚动)。"""
    if win.title == "Cursor Agents":
        cx = win.left + int(win.width * 0.55)
        cy = win.top + int(win.height * 0.58)
    else:
        cx = win.left + int(win.width * 0.72)
        cy = win.top + int(win.height * 0.55)
    return cx, cy


def scroll_composer_to_bottom(
    win: CursorWindow,
    *,
    restore_focus: bool = True,
    force: bool = False,
) -> bool:
    """把 Composer 聊天滚到最底, 让底部 Run/Fetch 等按钮进入截图可见区域。"""
    if not is_composer_window(win.title):
        return False

    now = time.monotonic()
    if not force and now - _last_composer_scroll.get(win.hwnd, 0) < _COMPOSER_SCROLL_COOLDOWN:
        return False

    import pyautogui

    prev_hwnd = user32.GetForegroundWindow()
    prev_mouse = pyautogui.position()

    _force_foreground(win.hwnd)
    time.sleep(0.1)

    cx, cy = _composer_click_point(win)
    pyautogui.click(cx, cy)
    time.sleep(0.06)

    pyautogui.hotkey("ctrl", "end")
    time.sleep(0.08)
    for _ in range(4):
        pyautogui.press("end")
        time.sleep(0.03)
    pyautogui.moveTo(cx, cy)
    for _ in range(8):
        pyautogui.scroll(-600)
        time.sleep(0.02)

    _last_composer_scroll[win.hwnd] = now

    if restore_focus and prev_hwnd and prev_hwnd != win.hwnd:
        time.sleep(0.04)
        _force_foreground(prev_hwnd)
    try:
        pyautogui.moveTo(prev_mouse.x, prev_mouse.y)
    except Exception:
        pass
    return True


def get_foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow() or 0)


def restore_foreground(hwnd: int) -> None:
    if hwnd:
        _force_foreground(hwnd)


def activate_window_for_scan(win: CursorWindow, settle: float = 0.1) -> None:
    """扫描前切到目标窗口, 确保后台多窗口也能截到最新画面。"""
    if win32gui.IsIconic(win.hwnd):
        user32.ShowWindow(win.hwnd, SW_RESTORE)
        time.sleep(0.1)
    _force_foreground(win.hwnd)
    time.sleep(settle)


def agents_sidebar_chat_points(win: CursorWindow, rows: int = 4) -> list[tuple[int, int]]:
    """Cursor Agents 左侧会话列表, 从上到下依次点(覆盖近期对话)。"""
    x = win.left + int(win.width * 0.08)
    y0 = win.top + 165
    step = max(52, int(win.height * 0.065))
    return [(x, y0 + i * step) for i in range(rows)]


def capture_window(hwnd: int, *, refresh_background: bool = True) -> np.ndarray | None:
    """抓取窗口画面; 目标窗口已是前台时直接截, 否则尝试 PrintWindow / 短暂激活。"""
    if win32gui.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.12)

    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        img = _capture_printwindow(hwnd)
        if img is not None and _is_good_capture(img):
            return img

    img = _capture_printwindow(hwnd)
    if img is not None and _is_good_capture(img):
        return img

    if not refresh_background:
        return img

    now = time.monotonic()
    last = _last_foreground_refresh.get(hwnd, 0.0)
    if now - last < _FOREGROUND_REFRESH_COOLDOWN and fg != hwnd:
        return img

    prev = fg
    _force_foreground(hwnd)
    time.sleep(0.12)
    _last_foreground_refresh[hwnd] = now
    img2 = _capture_printwindow(hwnd)
    if prev and prev != hwnd:
        time.sleep(0.04)
        _force_foreground(prev)
    if img2 is not None and _is_good_capture(img2):
        return img2
    return img2 or img


def _force_foreground(hwnd: int) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    cur_thread = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tgt_thread = user32.GetWindowThreadProcessId(hwnd, None)
    attached = []
    if fg_thread and fg_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, fg_thread, True)
        attached.append(fg_thread)
    if tgt_thread and tgt_thread != cur_thread and tgt_thread != fg_thread:
        user32.AttachThreadInput(cur_thread, tgt_thread, True)
        attached.append(tgt_thread)
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        for t in attached:
            user32.AttachThreadInput(cur_thread, t, False)
    return user32.GetForegroundWindow() == hwnd


def focus_and_click(
    hwnd: int, screen_x: int, screen_y: int,
    restore_focus: bool = True, restore_mouse: bool = True, settle: float = 0.12,
) -> bool:
    import pyautogui

    prev_hwnd = user32.GetForegroundWindow()
    prev_mouse = pyautogui.position()

    _force_foreground(hwnd)
    time.sleep(settle)
    pyautogui.click(screen_x, screen_y)

    if restore_mouse:
        try:
            pyautogui.moveTo(prev_mouse.x, prev_mouse.y)
        except Exception:
            pass
    if restore_focus and prev_hwnd and prev_hwnd != hwnd:
        time.sleep(0.05)
        try:
            _force_foreground(prev_hwnd)
        except Exception:
            pass
    return True
