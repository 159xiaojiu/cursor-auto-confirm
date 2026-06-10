"""阶段1: 屏幕截取。基于 mss, 支持多显示器与区域裁剪。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from mss import mss


@dataclass
class CaptureResult:
    image: np.ndarray          # BGR 图像 (H, W, 3)
    offset_x: int              # 截图左上角在虚拟屏幕中的 x
    offset_y: int              # 截图左上角在虚拟屏幕中的 y
    scale: float               # 相对原始像素的缩放比(downscale 用)


class ScreenCapturer:
    """抓取指定显示器/区域的截图。

    monitor: 0 = 所有显示器拼合的虚拟屏幕; 1..N = 第 N 块显示器。
    region:  [left, top, width, height] 相对所选显示器左上角的裁剪区; None = 整块。
    """

    def __init__(
        self,
        monitor: int = 0,
        region: list[int] | None = None,
        downscale: float = 1.0,
    ) -> None:
        self.monitor = monitor
        self.region = region
        self.downscale = downscale if downscale and downscale > 0 else 1.0
        self._sct = mss()
        self._mon_box = self._resolve_monitor_box()

    def _resolve_monitor_box(self) -> dict:
        monitors = self._sct.monitors  # [0]=虚拟全屏, [1..]=各显示器
        if self.monitor < 0 or self.monitor >= len(monitors):
            self.monitor = 0
        base = monitors[self.monitor]

        if self.region:
            left = base["left"] + int(self.region[0])
            top = base["top"] + int(self.region[1])
            width = int(self.region[2])
            height = int(self.region[3])
            return {"left": left, "top": top, "width": width, "height": height}
        return dict(base)

    def monitor_count(self) -> int:
        return max(0, len(self._sct.monitors) - 1)

    def grab(self) -> CaptureResult:
        box = self._mon_box
        shot = self._sct.grab(box)
        # mss 返回 BGRA, 转 BGR(opencv/rapidocr 友好)
        img = np.array(shot)  # (H, W, 4) BGRA
        img = img[:, :, :3]   # 去掉 alpha -> BGR

        scale = 1.0
        if self.downscale != 1.0:
            new_w = max(1, int(img.shape[1] * self.downscale))
            new_h = max(1, int(img.shape[0] * self.downscale))
            import cv2

            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            scale = self.downscale

        return CaptureResult(
            image=img,
            offset_x=box["left"],
            offset_y=box["top"],
            scale=scale,
        )
