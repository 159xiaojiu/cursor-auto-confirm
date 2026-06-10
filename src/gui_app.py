"""桌面小窗口应用: 像普通软件一样在任务栏显示, 一键启停。

双击桌面图标 -> 弹出小窗口(任务栏可见)
  [启动自动点击] [停止] [退出]
"""
from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.paths import project_root
    from src.process_manager import is_worker_running, start_worker, stop_worker
else:
    from .paths import project_root
    from src.process_manager import is_worker_running, start_worker, stop_worker

APP_LOCK = os.path.join(project_root(), "app.lock")
POLL_MS = 1500


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


def acquire_app_lock() -> bool:
    if os.path.exists(APP_LOCK):
        try:
            with open(APP_LOCK, "r", encoding="ascii") as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return False
        except (ValueError, OSError):
            pass
    with open(APP_LOCK, "w", encoding="ascii") as f:
        f.write(str(os.getpid()))
    return True


def release_app_lock() -> None:
    try:
        if os.path.exists(APP_LOCK):
            os.remove(APP_LOCK)
    except OSError:
        pass


def _icon_path() -> str | None:
    for rel in ("assets/app.ico", "_internal/assets/app.ico"):
        p = os.path.join(project_root(), rel)
        if os.path.isfile(p):
            return p
    return None


class AutoConfirmApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Cursor 自动确认")
        self.root.resizable(False, False)
        self.root.geometry("380x240")
        self.root.minsize(380, 240)

        ico = _icon_path()
        if ico:
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

        self._closing = False
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self._center_window()
        self._poll_status()

    def _center_window(self) -> None:
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 40
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Cursor 自动确认助手",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(pady=(0, 8))

        self.status_var = tk.StringVar(value="状态: 检查中…")
        self.status_label = ttk.Label(
            outer, textvariable=self.status_var, font=("Microsoft YaHei UI", 11)
        )
        self.status_label.pack(pady=4)

        ttk.Label(
            outer,
            text="自动点击所有 Cursor 窗口的 Accept / Run / Continue",
            font=("Microsoft YaHei UI", 9),
            foreground="#64748B",
            wraplength=340,
            justify=tk.CENTER,
        ).pack(pady=(0, 16))

        btn_row = ttk.Frame(outer)
        btn_row.pack(pady=4)

        self.btn_start = tk.Button(
            btn_row,
            text="▶  启动",
            font=("Microsoft YaHei UI", 11),
            width=10,
            bg="#10B981",
            fg="white",
            activebackground="#059669",
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self.on_start,
        )
        self.btn_start.pack(side=tk.LEFT, padx=6)

        self.btn_stop = tk.Button(
            btn_row,
            text="■  停止",
            font=("Microsoft YaHei UI", 11),
            width=10,
            bg="#64748B",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self.on_stop,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=6)

        ttk.Button(outer, text="退出程序", command=self.on_exit).pack(pady=(14, 0))

    def _set_status(self, running: bool) -> None:
        if running:
            self.status_var.set("● 运行中 — 正在自动帮你点确认")
            self.status_label.configure(foreground="#10B981")
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.status_var.set("○ 已停止")
            self.status_label.configure(foreground="#64748B")
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)

    def _poll_status(self) -> None:
        if not self._closing:
            self._set_status(is_worker_running())
            self.root.after(POLL_MS, self._poll_status)

    def on_start(self) -> None:
        try:
            start_worker()
            time.sleep(0.6)
        except Exception as e:
            messagebox.showerror("启动失败", str(e), parent=self.root)
        self._set_status(is_worker_running())

    def on_stop(self) -> None:
        stop_worker()
        time.sleep(0.2)
        self._set_status(is_worker_running())

    def on_exit(self) -> None:
        if not messagebox.askyesno(
            "退出",
            "确定退出程序？\n（会先停止自动点击）",
            parent=self.root,
        ):
            return
        self._closing = True
        stop_worker()
        self.root.destroy()
        release_app_lock()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    if not acquire_app_lock():
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                "程序已在运行，请查看任务栏窗口。",
                "Cursor 自动确认",
                0x40,
            )
        except Exception:
            pass
        return 0
    try:
        AutoConfirmApp().run()
    finally:
        release_app_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
