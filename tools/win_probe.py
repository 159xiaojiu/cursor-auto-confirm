"""诊断: 枚举 Cursor 窗口并测试后台离屏抓取(PrintWindow)是否可行。

输出每个 Cursor 窗口的句柄/标题/状态, 并尝试 PrintWindow 抓图,
报告抓到的画面是否非黑(可用于离屏 OCR)。抓到的缩略图存到 tools/_probe/。
"""
from __future__ import annotations

import os
import sys

import numpy as np
import win32con
import win32gui
import win32process
import win32ui
from ctypes import windll

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe")
os.makedirs(OUT_DIR, exist_ok=True)

PW_RENDERFULLCONTENT = 0x00000002


from ctypes import create_unicode_buffer, byref, c_uint

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def proc_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        h = windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return "?"
        buf = create_unicode_buffer(1024)
        size = c_uint(1024)
        ok = windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, byref(size))
        windll.kernel32.CloseHandle(h)
        if ok:
            return os.path.basename(buf.value)
        return "?"
    except Exception:
        return "?"


def capture_printwindow(hwnd: int):
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
    result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
    bmpinfo = bmp.GetInfo()
    bmpstr = bmp.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
        (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)
    )
    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return result, img[:, :, :3]


def main():
    targets = []

    all_titled = []

    def cb(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        name = proc_name(hwnd)
        all_titled.append((hwnd, title, name))
        if name.lower() == "cursor.exe":
            targets.append((hwnd, title, name))

    win32gui.EnumWindows(cb, None)

    print("=== 所有带标题的可见窗口(进程名 | 标题) ===")
    for hwnd, title, name in all_titled:
        print(f"  {name:24} | {title[:70]}")
    print()

    print(f"找到 {len(targets)} 个 Cursor 顶层窗口:")
    for i, (hwnd, title, name) in enumerate(targets):
        visible = win32gui.IsWindowVisible(hwnd)
        minimized = win32gui.IsIconic(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        print(f"\n[{i}] hwnd={hwnd} '{title[:60]}'")
        print(f"    visible={visible} minimized={minimized} rect={rect}")
        try:
            res, img = capture_printwindow(hwnd)
            nonblack = float((img.sum(axis=2) > 30).mean())
            mean = float(img.mean())
            print(f"    PrintWindow ret={res} 画面均值={mean:.1f} 非黑像素比={nonblack:.1%}")
            try:
                from PIL import Image

                Image.fromarray(img[:, :, ::-1]).save(
                    os.path.join(OUT_DIR, f"win_{i}.png")
                )
            except Exception as e:
                print(f"    存图失败: {e}")
            # 对主编辑窗口(够大)跑一次 OCR, 验证离屏识别可行
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w >= 400 and h >= 300:
                _ocr_report(img)
        except Exception as e:
            print(f"    抓取失败: {e}")


_DET = None


def _ocr_report(img):
    global _DET
    if _DET is None:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.config import load_config
        from src.detector import ButtonDetector

        cfg = load_config()
        _DET = ButtonDetector(cfg.detection)
    from src.capture import CaptureResult

    cap = CaptureResult(image=img, offset_x=0, offset_y=0, scale=1.0)
    candidates, boxes = _DET.detect(cap)
    print(f"    OCR 文本块数={len(boxes)}; 识别到的疑似按钮文字: "
          f"{[b.text for b in boxes if len(b.text) <= 20][:15]}")
    if candidates:
        print(f"    >>> 命中目标按钮: "
              f"{[(c.label, c.box.left, c.box.top) for c in candidates]}")


if __name__ == "__main__":
    sys.exit(main())
