"""安全网关单元测试: 危险命令拦截 + 死循环检测(不依赖 OCR)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import SafetyConfig, DeathLoopConfig
from src.detector import ButtonCandidate, TextBox
from src.safety import SafetyGate


def _make_candidate(label, x=500, y=800, top=790, bottom=810, left=480, right=520):
    box = TextBox(text=label, cx=x, cy=y, left=left, top=top,
                  right=right, bottom=bottom, score=0.95)
    return ButtonCandidate(label=label, box=box, screen_x=x, screen_y=y)


def _cfg(**kw):
    cfg = SafetyConfig(
        enabled=True,
        command_buttons=["Run", "Approve"],
        command_lookup_height=400,
        dangerous_patterns=["rm -rf", "format c:", "| sh"],
        death_loop=DeathLoopConfig(window_seconds=60, max_clicks=3, cooldown_seconds=120),
    )
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def test_dangerous_command_blocked():
    gate = SafetyGate(_cfg())
    run_btn = _make_candidate("Run")
    # 命令文本在按钮上方
    cmd_box = TextBox(text="sudo rm -rf /var/data", cx=500, cy=600,
                      left=400, top=590, right=700, bottom=610, score=0.9)
    decision = gate.check_dangerous(run_btn, [run_btn.box, cmd_box])
    assert decision.allow is False
    assert "rm -rf" in decision.reason


def test_safe_command_allowed():
    gate = SafetyGate(_cfg())
    run_btn = _make_candidate("Run")
    cmd_box = TextBox(text="npm install", cx=500, cy=600,
                      left=400, top=590, right=700, bottom=610, score=0.9)
    decision = gate.check_dangerous(run_btn, [run_btn.box, cmd_box])
    assert decision.allow is True


def test_non_command_button_skips_danger_check():
    gate = SafetyGate(_cfg())
    accept = _make_candidate("Accept")
    # 即便屏幕上有危险文本, 非命令型按钮不做命令检查
    danger = TextBox(text="rm -rf /", cx=500, cy=600,
                     left=400, top=590, right=700, bottom=610, score=0.9)
    assert gate.check_dangerous(accept, [accept.box, danger]).allow is True


def test_death_loop_triggers_cooldown():
    gate = SafetyGate(_cfg())
    btn = _make_candidate("Continue")
    # max_clicks=3: 前 3 次允许, 第 4 次应触发
    for _ in range(3):
        assert gate.check_death_loop(btn).allow is True
        gate.record_click(btn)
    blocked = gate.check_death_loop(btn)
    assert blocked.allow is False
    assert gate.in_cooldown() is True
