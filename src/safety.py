"""阶段4: 安全网关。

1) 危险命令拦截: 对 Run/Approve 等命令型按钮, 读取按钮上方的命令文本,
   命中危险模式则拦截。
2) 死循环检测: 同一按钮在时间窗内被点击过多次时暂停告警。
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from .config import SafetyConfig
from .detector import ButtonCandidate, TextBox


@dataclass
class SafetyDecision:
    allow: bool
    reason: str = ""


class SafetyGate:
    def __init__(self, cfg: SafetyConfig) -> None:
        self.cfg = cfg
        self.command_buttons = {b.lower() for b in cfg.command_buttons}
        self.dangerous = [p.lower() for p in cfg.dangerous_patterns]
        # 记录最近点击: (label, x_bucket, y_bucket, timestamp)
        self._clicks: deque[tuple[str, int, int, float]] = deque(maxlen=200)
        self._cooldown_until = 0.0

    # ---------- 危险命令 ----------
    def _is_command_button(self, label: str) -> bool:
        return label.lower() in self.command_buttons

    def _collect_command_text(
        self, candidate: ButtonCandidate, all_boxes: list[TextBox]
    ) -> str:
        """收集按钮上方一定范围内的文本, 作为待执行命令的近似。"""
        btn = candidate.box
        top_limit = btn.top - self.cfg.command_lookup_height
        parts: list[str] = []
        for b in all_boxes:
            if b is btn:
                continue
            # 在按钮上方, 且与按钮水平有交叠或邻近
            if b.bottom <= btn.cy and b.bottom >= top_limit:
                horizontally_near = not (b.right < btn.left - 600 or b.left > btn.right + 600)
                if horizontally_near:
                    parts.append(b.text)
        return " ".join(parts).lower()

    def check_dangerous(
        self, candidate: ButtonCandidate, all_boxes: list[TextBox]
    ) -> SafetyDecision:
        if not self.cfg.enabled:
            return SafetyDecision(True)
        if not self._is_command_button(candidate.label):
            return SafetyDecision(True)
        text = self._collect_command_text(candidate, all_boxes)
        for pat in self.dangerous:
            if pat and pat in text:
                return SafetyDecision(False, f"检测到危险命令模式: '{pat}'")
        return SafetyDecision(True)

    # ---------- 死循环 ----------
    def in_cooldown(self) -> bool:
        return time.monotonic() < self._cooldown_until

    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown_until - time.monotonic())

    def check_death_loop(self, candidate: ButtonCandidate) -> SafetyDecision:
        dl = self.cfg.death_loop
        now = time.monotonic()
        bx = int(candidate.screen_x // 40)
        by = int(candidate.screen_y // 40)
        window_start = now - dl.window_seconds
        count = sum(
            1
            for (label, x, y, ts) in self._clicks
            if ts >= window_start and label == candidate.label and x == bx and y == by
        )
        if count >= dl.max_clicks:
            self._cooldown_until = now + dl.cooldown_seconds
            return SafetyDecision(
                False,
                f"疑似死循环: '{candidate.label}' 在 {dl.window_seconds:.0f}s 内点击 "
                f"{count} 次, 暂停 {dl.cooldown_seconds:.0f}s",
            )
        return SafetyDecision(True)

    def record_click(self, candidate: ButtonCandidate) -> None:
        bx = int(candidate.screen_x // 40)
        by = int(candidate.screen_y // 40)
        self._clicks.append((candidate.label, bx, by, time.monotonic()))

    def evaluate(
        self, candidate: ButtonCandidate, all_boxes: list[TextBox]
    ) -> SafetyDecision:
        if self.in_cooldown():
            return SafetyDecision(False, f"冷却中(剩余 {self.cooldown_remaining():.0f}s)")
        loop = self.check_death_loop(candidate)
        if not loop.allow:
            return loop
        danger = self.check_dangerous(candidate, all_boxes)
        if not danger.allow:
            return danger
        return SafetyDecision(True)
