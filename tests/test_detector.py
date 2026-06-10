"""检测器集成测试: 合成按钮图片 -> OCR -> 匹配 -> 黑名单过滤。

依赖 OCR 模型(首次需联网下载)。若环境无 OCR 则跳过。
"""
import os
import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.capture import CaptureResult
from src.config import DetectionConfig
from src.detector import ButtonDetector


def _make_button_image() -> np.ndarray:
    """白底黑字, 画几个按钮样式文本。"""
    img = Image.new("RGB", (900, 500), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    draw.text((60, 60), "Accept All", fill=(0, 0, 0), font=font)
    draw.text((60, 200), "Run", fill=(0, 0, 0), font=font)
    draw.text((60, 340), "Reject", fill=(0, 0, 0), font=font)
    # PIL 是 RGB, 转 BGR 以匹配采集管线
    return np.array(img)[:, :, ::-1].copy()


@pytest.fixture(scope="module")
def detector():
    cfg = DetectionConfig(
        min_confidence=0.3,
        targets=["Accept All", "Accept", "Run"],
        blacklist=["Reject", "Undo"],
    )
    det = ButtonDetector(cfg)
    try:
        det._ensure_engine()
    except Exception as e:
        pytest.skip(f"OCR 引擎不可用: {e}")
    return det


def test_detects_targets_and_filters_blacklist(detector):
    img = _make_button_image()
    capture = CaptureResult(image=img, offset_x=100, offset_y=50, scale=1.0)
    candidates, boxes = detector.detect(capture)

    labels = {c.label for c in candidates}
    assert "Accept All" in labels, f"OCR 文本框: {[b.text for b in boxes]}"
    assert "Run" in labels
    # Reject 在黑名单, 不应作为候选
    assert "Reject" not in labels


def test_match_label_rejects_code_identifiers():
    """匹配规则不应把代码里的 run_gui()/accepted 误判成按钮。"""
    cfg = DetectionConfig(
        min_confidence=0.3,
        targets=["Accept All", "Accept", "Run"],
        blacklist=[],
    )
    det = ButtonDetector(cfg)
    assert det._match_label("run") == "Run"
    assert det._match_label("run ⌘↵") == "Run"
    assert det._match_label("accept all") == "Accept All"
    # 这些都不该匹配
    assert det._match_label("run_gui()") is None
    assert det._match_label("run()") is None
    assert det._match_label("running") is None
    assert det._match_label("accepted") is None
    assert det._match_label("runner") is None


def test_screen_coordinate_offset_applied(detector):
    img = _make_button_image()
    capture = CaptureResult(image=img, offset_x=100, offset_y=50, scale=1.0)
    candidates, _ = detector.detect(capture)
    assert candidates, "应至少检测到一个按钮"
    # 偏移量应被叠加(offset_x=100) -> 屏幕坐标 >= 100
    for c in candidates:
        assert c.screen_x >= 100
        assert c.screen_y >= 50
