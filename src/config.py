"""配置加载与默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

from .paths import config_path as _default_config_path


def DEFAULT_CONFIG_PATH() -> str:
    return _default_config_path()


@dataclass
class ScanConfig:
    interval_seconds: float = 1.5
    monitor: int = 0
    region: list[int] | None = None
    downscale: float = 1.0
    mode: str = "windows"   # windows=逐个Cursor窗口(支持后台/多窗口); screen=整屏


@dataclass
class DetectionConfig:
    min_confidence: float = 0.5
    targets: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)


@dataclass
class DeathLoopConfig:
    window_seconds: float = 60.0
    max_clicks: int = 5
    cooldown_seconds: float = 120.0


@dataclass
class SafetyConfig:
    enabled: bool = True
    command_buttons: list[str] = field(default_factory=list)
    command_lookup_height: int = 420
    dangerous_patterns: list[str] = field(default_factory=list)
    death_loop: DeathLoopConfig = field(default_factory=DeathLoopConfig)


@dataclass
class ClickConfig:
    restore_focus: bool = True
    restore_mouse: bool = True
    pause_on_user_activity_seconds: float = 2.0


@dataclass
class HotkeyConfig:
    toggle: str = "ctrl+alt+a"
    quit: str = "ctrl+alt+q"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/autopilot.log"


@dataclass
class WatchdogConfig:
    enabled: bool = True
    interval_seconds: float = 300.0   # 默认每 5 分钟巡检一次


@dataclass
class AppConfig:
    scan: ScanConfig = field(default_factory=ScanConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    click: ClickConfig = field(default_factory=ClickConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    watchdog: WatchdogConfig = field(default_factory=WatchdogConfig)


def _merge(section: dict[str, Any] | None, target: Any) -> None:
    """把 yaml 中的字段覆盖到 dataclass 实例上(浅层)。"""
    if not section:
        return
    for key, value in section.items():
        if hasattr(target, key):
            setattr(target, key, value)


def load_config(path: str | None = None) -> AppConfig:
    path = path or DEFAULT_CONFIG_PATH()
    cfg = AppConfig()
    if not os.path.exists(path):
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _merge(data.get("scan"), cfg.scan)
    _merge(data.get("detection"), cfg.detection)

    safety_data = data.get("safety") or {}
    death_loop_data = safety_data.pop("death_loop", None)
    _merge(safety_data, cfg.safety)
    if death_loop_data:
        _merge(death_loop_data, cfg.safety.death_loop)

    _merge(data.get("click"), cfg.click)
    _merge(data.get("hotkey"), cfg.hotkey)
    _merge(data.get("logging"), cfg.logging)
    _merge(data.get("watchdog"), cfg.watchdog)
    return cfg
