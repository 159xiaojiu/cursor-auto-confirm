"""ConversationWatchdog 单元测试。"""
from src.detector import ButtonCandidate, TextBox
from src.safety import SafetyGate
from src.config import SafetyConfig
from src.detector import ButtonDetector
from src.config import DetectionConfig
from src.watchdog import ConversationWatchdog


def _cand(label: str) -> ButtonCandidate:
    box = TextBox(text=label, cx=100, cy=200, left=80, top=190, right=120, bottom=210, score=0.99)
    return ButtonCandidate(label=label, box=box, screen_x=500, screen_y=600)


def test_watchdog_stuck_pending():
    det = ButtonDetector(DetectionConfig(targets=["Run"]))
    safety = SafetyGate(SafetyConfig(enabled=False))
    wd = ConversationWatchdog(det, safety)
    fake_win = type("W", (), {"title": "Cursor Agents"})()
    reports = wd.check_windows(
        [(fake_win, [_cand("Run")], [])],
        autopilot_enabled=True,
    )
    assert reports[0].state == "stuck_pending"
    assert "Run" in reports[0].pending


def test_watchdog_running_ok():
    det = ButtonDetector(DetectionConfig())
    safety = SafetyGate(SafetyConfig())
    wd = ConversationWatchdog(det, safety)
    fake_win = type("W", (), {"title": "Cursor Agents"})()
    boxes = [TextBox(text="Exploring", cx=0, cy=0, left=0, top=0, right=10, bottom=10, score=1.0)]
    reports = wd.check_windows([(fake_win, [], boxes)])
    assert reports[0].state == "running_ok"


def test_watchdog_skips_home_in_check():
    det = ButtonDetector(DetectionConfig())
    safety = SafetyGate(SafetyConfig())
    wd = ConversationWatchdog(det, safety)
    fake_win = type("W", (), {"title": "Cursor"})()
    reports = wd.check_windows([(fake_win, [_cand("Run")], [])])
    assert reports == []
