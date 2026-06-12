"""对话窗口巡检: 周期性检查 Cursor 是否在跑、是否有未点的确认按钮。"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .detector import ButtonCandidate, ButtonDetector, TextBox
from .safety import SafetyGate
from .windows import list_cursor_windows

if TYPE_CHECKING:
    from .main import Orchestrator

log = logging.getLogger("autopilot.watchdog")

_RUNNING_HINTS = (
    "exploring", "generating", "thought", "planning", "working",
    "stop ctrl", "local", "cloud",
)
_DONE_HINTS = ("ran ", "ran\n", "completed", "finished", "done")


@dataclass
class WindowReport:
    title: str
    state: str  # idle | running_ok | completed | stuck_pending | blocked
    pending: list[str] = field(default_factory=list)
    activity: list[str] = field(default_factory=list)
    block_reason: str = ""
    capture_ok: bool = True


class ConversationWatchdog:
    """每 N 秒巡检一次 Cursor 对话窗口健康状态。"""

    def __init__(self, detector: ButtonDetector, safety: SafetyGate) -> None:
        self.detector = detector
        self.safety = safety
        self._last_check = 0.0
        self._stuck_since: dict[str, float] = {}

    def due(self, interval: float, now: float | None = None) -> bool:
        now = now or time.monotonic()
        return (now - self._last_check) >= interval

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _activity_from_boxes(self, boxes: list[TextBox]) -> tuple[list[str], bool, bool]:
        running: list[str] = []
        done = False
        for b in boxes:
            t = self._norm(b.text)
            if not t:
                continue
            if any(h in t for h in _RUNNING_HINTS) or t == "stop":
                running.append(b.text.strip())
            if any(h in t for h in _DONE_HINTS):
                done = True
            if re.search(r"\b\d{1,3}%\b", t):
                running.append(b.text.strip())
        return running, bool(running), done

    def _classify(
        self,
        title: str,
        candidates: list[ButtonCandidate],
        boxes: list[TextBox],
        *,
        autopilot_enabled: bool,
    ) -> WindowReport:
        activity, is_running, is_done = self._activity_from_boxes(boxes)
        pending_labels = [c.label for c in candidates]
        block_reason = ""

        if candidates:
            for c in candidates:
                decision = self.safety.evaluate(
                    c, getattr(c, "safety_boxes", None) or boxes
                )
                if not decision.allow:
                    block_reason = decision.reason
                    return WindowReport(
                        title=title,
                        state="blocked",
                        pending=pending_labels,
                        activity=activity,
                        block_reason=block_reason,
                    )
            if not autopilot_enabled:
                return WindowReport(
                    title=title,
                    state="stuck_pending",
                    pending=pending_labels,
                    activity=activity,
                    block_reason="自动点击已暂停(Ctrl+Alt+A)",
                )
            return WindowReport(
                title=title,
                state="stuck_pending",
                pending=pending_labels,
                activity=activity,
            )

        if is_running:
            return WindowReport(title=title, state="running_ok", activity=activity)
        if is_done:
            return WindowReport(title=title, state="completed", activity=activity)
        return WindowReport(title=title, state="idle", activity=activity)

    def check_windows(
        self,
        window_results: list[tuple],
        *,
        autopilot_enabled: bool = True,
    ) -> list[WindowReport]:
        reports: list[WindowReport] = []
        for win, candidates, activity_boxes in window_results:
            if win.title == "Cursor":
                continue
            all_boxes: list[TextBox] = list(activity_boxes)
            for c in candidates:
                sb = getattr(c, "safety_boxes", None)
                if sb:
                    all_boxes.extend(sb)
            reports.append(
                self._classify(
                    win.title, candidates, all_boxes, autopilot_enabled=autopilot_enabled
                )
            )
        return reports

    def run_check(
        self,
        window_results: list[tuple],
        *,
        autopilot_enabled: bool = True,
        interval: float = 180.0,
        retry_on_stuck: bool = True,
        orchestrator: Orchestrator | None = None,
    ) -> list[WindowReport]:
        now = time.monotonic()
        if not self.due(interval, now):
            return []
        self._last_check = now

        all_cursor = list_cursor_windows()
        monitored = [w.title for w in all_cursor if w.title != "Cursor"]
        skipped = [w.title for w in all_cursor if w.title == "Cursor"]
        log.info(
            "【巡检】Cursor 窗口共 %d 个 | 监控: %s | 跳过(Home欢迎页): %s",
            len(all_cursor), monitored or "无", skipped or "无",
        )

        if not autopilot_enabled:
            log.warning("【巡检】自动点击当前已暂停 (Ctrl+Alt+A 可恢复)")

        if self.safety.in_cooldown():
            log.warning(
                "【巡检】安全冷却中, 暂停点击 (剩余 %.0fs)",
                self.safety.cooldown_remaining(),
            )

        reports = self.check_windows(
            window_results, autopilot_enabled=autopilot_enabled
        )
        if not reports:
            log.info("【巡检】无 Agent 对话窗口需要照看")
            return reports

        lines = ["【巡检】对话窗口状态 (每 %.0f 分钟)" % (interval / 60.0)]
        stuck_titles: list[str] = []
        for r in reports:
            if r.state == "stuck_pending":
                self._stuck_since.setdefault(r.title, now)
                stuck_sec = int(now - self._stuck_since[r.title])
                stuck_titles.append(r.title)
                msg = (
                    f"  ⚠ {r.title}: 有待确认但未自动点击 "
                    f"按钮={r.pending} 已等待约{stuck_sec}s"
                )
                if r.block_reason:
                    msg += f" ({r.block_reason})"
                lines.append(msg)
                log.warning("【巡检】'%s' 待点 %s 未自动点击(约 %ds)", r.title, r.pending, stuck_sec)
            elif r.state == "blocked":
                self._stuck_since.setdefault(r.title, now)
                lines.append(
                    f"  ⛔ {r.title}: 检测到 {r.pending} 但被安全拦截: {r.block_reason}"
                )
                log.warning("【巡检】'%s' 待点 %s 被拦截: %s", r.title, r.pending, r.block_reason)
            elif r.state == "running_ok":
                self._stuck_since.pop(r.title, None)
                act = ", ".join(r.activity[:2]) if r.activity else "运行中"
                lines.append(f"  ✓ {r.title}: Agent 运行中, 暂无待确认 ({act})")
            elif r.state == "completed":
                self._stuck_since.pop(r.title, None)
                lines.append(f"  ✓ {r.title}: 当前步骤已完成, 无待确认按钮")
            else:
                self._stuck_since.pop(r.title, None)
                lines.append(f"  · {r.title}: 空闲/无 Agent 任务")

        log.info("\n".join(lines))

        if (
            retry_on_stuck
            and stuck_titles
            and orchestrator is not None
            and autopilot_enabled
        ):
            for title in stuck_titles:
                log.info("【巡检】强制重扫并尝试点击: %s", title)
                orchestrator.retry_window(title)

        return reports
