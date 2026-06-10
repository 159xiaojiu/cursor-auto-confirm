"""应用图标生成: 托盘 / 桌面 / 打包用。"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont


# 运行中 = 翠绿; 已停止 = 石板灰
COLOR_ON = (16, 185, 129, 255)      # #10B981
COLOR_OFF = (100, 116, 139, 255)    # #64748B
COLOR_RING = (255, 255, 255, 200)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\arialbd.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_check(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float) -> None:
    """画清晰的白色对勾。"""
    pts = [
        (cx - 14 * scale, cy + 2 * scale),
        (cx - 4 * scale, cy + 12 * scale),
        (cx + 16 * scale, cy - 12 * scale),
    ]
    draw.line(pts[:2], fill=(255, 255, 255, 255), width=max(2, int(5 * scale)), joint="curve")
    draw.line(pts[1:], fill=(255, 255, 255, 255), width=max(2, int(5 * scale)), joint="curve")


def _draw_pointer(draw: ImageDraw.ImageDraw, size: int) -> None:
    """右下角小鼠标指针, 表示自动点击。"""
    s = size / 64.0
    x0, y0 = int(42 * s), int(42 * s)
    tri = [(x0, y0), (x0 + int(10 * s), y0 + int(16 * s)), (x0 + int(6 * s), y0 + int(10 * s))]
    draw.polygon(tri, fill=(255, 255, 255, 230))
    draw.line([(x0 + int(6 * s), y0 + int(10 * s)), (x0 + int(10 * s), y0 + int(16 * s))],
              fill=(30, 41, 59, 255), width=max(1, int(1.5 * s)))


def make_icon(running: bool, size: int = 64) -> Image.Image:
    """生成托盘图标。绿色对勾=运行中, 灰色对勾=已停止。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64.0
    margin = int(4 * s)
    bg = COLOR_ON if running else COLOR_OFF

    # 圆角方块底
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(14 * s),
        fill=bg,
    )
    # 内圈高光
    draw.rounded_rectangle(
        [margin + int(2 * s), margin + int(2 * s), size - margin - int(2 * s), size - margin - int(2 * s)],
        radius=int(12 * s),
        outline=COLOR_RING,
        width=max(1, int(2 * s)),
    )

    cx, cy = size * 0.46, size * 0.50
    _draw_check(draw, cx, cy, s)
    if running:
        _draw_pointer(draw, size)

    return img


def make_desktop_icon(size: int = 256) -> Image.Image:
    """桌面大图标: 更醒目, 带简短文字 Auto。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 256.0
    margin = int(16 * s)

    # 深蓝底 + 绿色强调条
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(48 * s),
        fill=(15, 23, 42, 255),
    )
    draw.rounded_rectangle(
        [margin, margin, size - margin, margin + int(56 * s)],
        radius=int(48 * s),
        fill=COLOR_ON,
    )

    cx, cy = size * 0.5, size * 0.46
    _draw_check(draw, cx, cy, s * 1.8)

    font = _load_font(int(36 * s))
    label = "Auto"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(
        ((size - tw) / 2, size * 0.72),
        label,
        fill=(255, 255, 255, 255),
        font=font,
    )
    sub_font = _load_font(int(18 * s))
    sub = "Confirm"
    bbox2 = draw.textbbox((0, 0), sub, font=sub_font)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(
        ((size - tw2) / 2, size * 0.84),
        sub,
        fill=(148, 163, 184, 255),
        font=sub_font,
    )
    return img


def export_icons(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    desktop = make_desktop_icon(256)
    desktop.save(os.path.join(out_dir, "app.ico"), format="ICO",
                 sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    make_icon(True, 64).save(os.path.join(out_dir, "tray_on.ico"), format="ICO",
                             sizes=[(64, 64), (32, 32), (16, 16)])
    make_icon(False, 64).save(os.path.join(out_dir, "tray_off.ico"), format="ICO",
                              sizes=[(64, 64), (32, 32), (16, 16)])
    desktop.save(os.path.join(out_dir, "app.png"))
