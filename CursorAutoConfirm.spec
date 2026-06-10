# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。运行 build_release.bat 生成可分享发布包。"""
import os
import sys

import rapidocr

block_cipher = None
ROOT = os.path.abspath(SPECPATH)
rapidocr_root = os.path.dirname(rapidocr.__file__)
rapidocr_models = os.path.join(rapidocr_root, "models")

# rapidocr 运行时需要 yaml 配置 + models, 不能只打包 models
rapidocr_datas = [
    (os.path.join(rapidocr_root, "default_models.yaml"), "rapidocr"),
    (os.path.join(rapidocr_root, "config.yaml"), "rapidocr"),
    (rapidocr_models, os.path.join("rapidocr", "models")),
]

a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "config.yaml"), "."),
        (os.path.join(ROOT, "assets"), "assets"),
        *rapidocr_datas,
    ],
    hiddenimports=[
        "rapidocr",
        "onnxruntime",
        "onnxruntime.capi.onnxruntime_pybind11_state",
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "win32timezone",
        "win32gui",
        "win32ui",
        "win32process",
        "win32api",
        "win32con",
        "keyboard",
        "mss",
        "cv2",
        "numpy",
        "yaml",
        "shapely",
        "pyclipper",
        "omegaconf",
        "colorlog",
        "src",
        "src.main",
        "src.gui_app",
        "src.tray_app",
        "src.paths",
        "src.process_manager",
        "src.icon_assets",
        "src.config",
        "src.capture",
        "src.detector",
        "src.safety",
        "src.clicker",
        "src.control",
        "src.windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CursorAutoConfirm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "app.ico") if os.path.exists(os.path.join(ROOT, "assets", "app.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CursorAutoConfirm",
)
