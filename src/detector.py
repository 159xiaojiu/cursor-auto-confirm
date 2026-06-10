"""阶段2: 按钮检测。

采用 OCR 优先策略: 全屏 OCR -> 匹配目标按钮文案 -> 返回候选。
无需预先采集模板, 对 Cursor 版本文案变化更鲁棒(模板匹配可后续作为增强)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .capture import CaptureResult
from .config import DetectionConfig


@dataclass
class TextBox:
    text: str
    cx: float          # 中心 x(截图坐标系)
    cy: float          # 中心 y
    left: float
    top: float
    right: float
    bottom: float
    score: float


@dataclass
class ButtonCandidate:
    label: str         # 命中的目标按钮名(来自 config.targets)
    box: TextBox
    screen_x: int      # 映射到物理屏幕的点击点 x
    screen_y: int
    hwnd: int | None = None   # windows 模式下所属 Cursor 窗口句柄


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _poly_to_box(poly) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


class ButtonDetector:
    def __init__(self, cfg: DetectionConfig) -> None:
        self.cfg = cfg
        # 长文案优先匹配, 避免 "Accept" 抢先于 "Accept All"
        self.targets = sorted(cfg.targets, key=len, reverse=True)
        self.targets_norm = [(_norm(t), t) for t in self.targets]
        self.blacklist_norm = [_norm(b) for b in cfg.blacklist]
        self._engine = None

    def _ensure_engine(self):
        if self._engine is None:
            try:
                # 新包 rapidocr (>=2.0)
                from rapidocr import RapidOCR
            except ImportError:
                # 旧包 rapidocr-onnxruntime
                from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    @staticmethod
    def _normalize_result(raw) -> list[tuple]:
        """把新旧两种 rapidocr 返回值统一成 [(poly, text, score), ...]。

        旧 API: engine(img) -> (list[[poly, text, score]], elapse)
        新 API: engine(img) -> RapidOCROutput(boxes, txts, scores)
        """
        # 旧 API: 元组 (result, elapse)
        if isinstance(raw, tuple) and len(raw) == 2 and not hasattr(raw, "boxes"):
            result = raw[0]
            return list(result) if result else []
        # 新 API: 带 boxes/txts/scores 属性的对象
        if hasattr(raw, "boxes") and hasattr(raw, "txts"):
            boxes = raw.boxes if raw.boxes is not None else []
            txts = raw.txts if raw.txts is not None else []
            scores = raw.scores if raw.scores is not None else []
            out = []
            for i in range(len(boxes)):
                poly = boxes[i]
                text = txts[i] if i < len(txts) else ""
                score = scores[i] if i < len(scores) else 0.0
                out.append((poly, text, score))
            return out
        # 兜底: 可迭代的 [(poly, text, score), ...]
        return list(raw) if raw else []

    def ocr(self, image: np.ndarray) -> list[TextBox]:
        engine = self._ensure_engine()
        raw = engine(image)
        items = self._normalize_result(raw)
        boxes: list[TextBox] = []
        for poly, text, score in items:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0
            if score < self.cfg.min_confidence:
                continue
            left, top, right, bottom = _poly_to_box(poly)
            boxes.append(
                TextBox(
                    text=text,
                    cx=(left + right) / 2.0,
                    cy=(top + bottom) / 2.0,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    score=score,
                )
            )
        return boxes

    def _is_blacklisted(self, norm_text: str) -> bool:
        for b in self.blacklist_norm:
            if not b:
                continue
            if norm_text == b or b in norm_text:
                return True
        return False

    def _match_label(self, norm_text: str) -> str | None:
        """把一个文本框匹配到目标按钮名。

        为避免误命中代码/正文里的词(如 run_gui()、accepted), 只接受:
          1) 完全等于按钮名;
          2) 按钮名 + 紧跟空白起始的快捷键提示(如 'run ⌘↵'), 且提示部分
             不含任何字母/数字/下划线。
        """
        # 1) 精确匹配优先
        for tnorm, original in self.targets_norm:
            if tnorm and norm_text == tnorm:
                return original
        # 2) 按钮名 + 快捷键提示
        for tnorm, original in self.targets_norm:
            if not tnorm or not norm_text.startswith(tnorm):
                continue
            rest = norm_text[len(tnorm):]
            if not rest or len(rest) > 8:
                continue
            if rest[0] not in " \t":
                continue  # 紧跟字符必须是空白(排除 run_gui / run() 之类)
            if any(c.isalnum() or c == "_" for c in rest):
                continue  # 提示部分不能含字母数字下划线
            return original
        return None

    def detect(
        self, capture: CaptureResult
    ) -> tuple[list[ButtonCandidate], list[TextBox]]:
        boxes = self.ocr(capture.image)
        candidates: list[ButtonCandidate] = []
        inv_scale = 1.0 / capture.scale if capture.scale else 1.0
        for box in boxes:
            norm_text = _norm(box.text)
            if self._is_blacklisted(norm_text):
                continue
            label = self._match_label(norm_text)
            if label is None:
                continue
            screen_x = int(capture.offset_x + box.cx * inv_scale)
            screen_y = int(capture.offset_y + box.cy * inv_scale)
            candidates.append(
                ButtonCandidate(
                    label=label, box=box, screen_x=screen_x, screen_y=screen_y
                )
            )
        # 按目标优先级排序(targets 顺序)
        order = {t: i for i, t in enumerate(self.targets)}
        candidates.sort(key=lambda c: order.get(c.label, 999))
        return candidates, boxes
