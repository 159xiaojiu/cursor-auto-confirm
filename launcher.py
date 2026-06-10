"""统一启动入口(开发 / 打包后均使用)。

双击 exe -> 桌面小窗口(任务栏可见), 一键启停
  CursorAutoConfirm.exe --worker -> 后台自动点击工作进程
  CursorAutoConfirm.exe --tray    -> 仅托盘模式(旧版)
"""
from __future__ import annotations

import sys


def main() -> int:
    if "--worker" in sys.argv:
        from src.main import main as worker_main

        sys.argv = [a for a in sys.argv if a != "--worker"]
        return worker_main()

    if "--tray" in sys.argv:
        from src.tray_app import main as tray_main

        return tray_main()

    from src.gui_app import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
