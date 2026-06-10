"""路径解析: 开发模式 vs PyInstaller 打包模式。"""
from __future__ import annotations

import os
import shutil
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> str:
    """可写目录: 日志/锁文件/config 放这里(与 exe 同目录)。"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_root() -> str:
    """只读资源目录(打包进 exe 内的 config/assets 等)。"""
    if is_frozen():
        return getattr(sys, "_MEIPASS", project_root())
    return project_root()


def config_path() -> str:
    """优先使用 exe 旁的可编辑 config.yaml; 首次运行从包内复制一份。"""
    user_cfg = os.path.join(project_root(), "config.yaml")
    if os.path.exists(user_cfg):
        return user_cfg
    bundled = os.path.join(bundle_root(), "config.yaml")
    if os.path.exists(bundled):
        try:
            shutil.copy2(bundled, user_cfg)
            return user_cfg
        except OSError:
            return bundled
    return user_cfg


def worker_command() -> list[str]:
    """启动后台工作进程的命令行。"""
    if is_frozen():
        return [sys.executable, "--worker"]
    venv_py = os.environ.get(
        "AUTOPILOT_PYTHONW",
        r"C:\Users\23986\autopilot_venv\Scripts\pythonw.exe",
    )
    if os.path.isfile(venv_py):
        return [venv_py, "-X", "utf8", "-m", "src.main"]
    return [sys.executable, "-X", "utf8", "-m", "src.main"]
