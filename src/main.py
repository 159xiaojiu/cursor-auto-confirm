"""主入口 + Orchestrator: 串联截屏 -> 检测 -> 安全 -> 点击 主循环。

用法:
    py -3.13 -m src.main                  # 正常运行
    py -3.13 -m src.main --once           # 只扫描一次并打印结果(自检/调试)
    py -3.13 -m src.main --dry-run        # 检测但不真正点击
    py -3.13 -m src.main --selftest       # 启动自检(依赖/显示器/OCR)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

# 允许以 `python src/main.py` 直接运行
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.capture import CaptureResult, ScreenCapturer
    from src.clicker import Clicker
    from src.config import AppConfig, load_config
    from src.control import HotkeyController, UserActivityMonitor
    from src.detector import ButtonDetector
    from src.safety import SafetyGate
    from src.watchdog import ConversationWatchdog
else:
    from .capture import CaptureResult, ScreenCapturer
    from .clicker import Clicker
    from .config import AppConfig, load_config
    from .control import HotkeyController, UserActivityMonitor
    from .detector import ButtonDetector
    from .safety import SafetyGate
    from .watchdog import ConversationWatchdog

log = logging.getLogger("autopilot")


def setup_logging(cfg: AppConfig) -> None:
    level = getattr(logging, cfg.logging.level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []
    # pythonw 无控制台时 sys.stdout 为 None, 跳过控制台输出
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    if cfg.logging.file:
        log_path = cfg.logging.file
        if not os.path.isabs(log_path):
            from .paths import project_root
            log_path = os.path.join(project_root(), log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def _project_root() -> str:
    from .paths import project_root
    return project_root()


def _pid_alive(pid: int) -> bool:
    """Windows 下判断进程是否存活。"""
    if pid <= 0:
        return False
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        # 非 Windows 兜底
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class SingleInstance:
    """用锁文件保证同一时间只有一个正式运行实例, 避免重复点击。"""

    def __init__(self) -> None:
        self.lock_path = os.path.join(_project_root(), "autopilot.lock")

    def existing_pid(self) -> int | None:
        if not os.path.exists(self.lock_path):
            return None
        try:
            with open(self.lock_path, "r", encoding="ascii") as f:
                pid = int(f.read().strip())
        except (ValueError, OSError):
            return None
        return pid if _pid_alive(pid) else None

    def acquire(self) -> bool:
        if self.existing_pid() is not None:
            return False
        with open(self.lock_path, "w", encoding="ascii") as f:
            f.write(str(os.getpid()))
        return True

    def release(self) -> None:
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except OSError:
            pass


class Orchestrator:
    def __init__(self, cfg: AppConfig, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.dry_run = dry_run
        self.capturer = ScreenCapturer(
            monitor=cfg.scan.monitor,
            region=cfg.scan.region,
            downscale=cfg.scan.downscale,
        )
        self.detector = ButtonDetector(cfg.detection)
        self.safety = SafetyGate(cfg.safety)
        self.clicker = Clicker(cfg.click)
        self.activity = UserActivityMonitor(cfg.click.pause_on_user_activity_seconds)
        self.hotkeys = HotkeyController(cfg.hotkey)
        self.watchdog = ConversationWatchdog(self.detector, self.safety)
        self._last_pause_log = 0.0
        self._last_cooldown_log = 0.0

    @property
    def windows_mode(self) -> bool:
        return self.cfg.scan.mode.lower() == "windows"

    def _log_pause_reasons(self) -> None:
        now = time.monotonic()
        if not self.hotkeys.enabled and now - self._last_pause_log > 60:
            log.warning("自动点击已暂停 (Ctrl+Alt+A 恢复)")
            self._last_pause_log = now
        if self.safety.in_cooldown() and now - self._last_cooldown_log > 30:
            log.warning(
                "安全冷却中, 暂停点击 (剩余 %.0fs)",
                self.safety.cooldown_remaining(),
            )
            self._last_cooldown_log = now

    def _ocr_region(self, win, region_img, y_off: int, x_off: int):
        from .capture import CaptureResult

        cap = CaptureResult(
            image=region_img,
            offset_x=win.left + x_off,
            offset_y=win.top + y_off,
            scale=1.0,
        )
        cands, boxes = self.detector.detect(cap)
        for c in cands:
            c.hwnd = win.hwnd
            c.safety_boxes = boxes
        return cands, boxes

    def _dedupe_candidates(self, all_cands: list) -> list:
        seen: set[tuple] = set()
        unique: list = []
        for c in all_cands:
            key = (c.label, c.screen_x // 24, c.screen_y // 24)
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        return unique

    def _scan_window(self, win, *, force_refresh: bool = False):
        from .windows import capture_window, is_composer_window, scroll_composer_to_bottom

        if is_composer_window(win.title):
            scroll_composer_to_bottom(win, force=force_refresh)

        refresh = force_refresh or win.title == "Cursor Agents"
        img = capture_window(win.hwnd, refresh_background=refresh)
        if img is None:
            log.debug("窗口 '%s' 截图失败", win.title)
            return [], []

        cands, boxes = self._scan_image_regions(win, img)
        if cands or not is_composer_window(win.title):
            return cands, boxes

        # 未找到按钮且聊天可能未滚到底: 强制滚到底后重扫一次
        log.debug("窗口 '%s' 未发现按钮, 强制滚到底后重试", win.title)
        scroll_composer_to_bottom(win, force=True)
        time.sleep(0.15)
        img2 = capture_window(win.hwnd, refresh_background=True)
        if img2 is None:
            return cands, boxes
        return self._scan_image_regions(win, img2)

    def _scan_image_regions(self, win, img):
        regions = self._scan_regions(win, img)
        if not regions:
            return [], []

        bottom = regions[-1]
        cands, boxes = self._ocr_region(win, bottom[0], bottom[1], bottom[2])
        if cands:
            return self._dedupe_candidates(cands), boxes

        all_cands: list = []
        all_boxes: list = []
        for region_img, y_off, x_off in regions:
            cands, boxes = self._ocr_region(win, region_img, y_off, x_off)
            all_cands.extend(cands)
            all_boxes.extend(boxes)
        return self._dedupe_candidates(all_cands), all_boxes

    def retry_window(self, title: str) -> bool:
        """巡检发现卡住时, 强制刷新指定窗口并重试点击。"""
        from .windows import list_cursor_windows

        clicked = False
        for win in list_cursor_windows():
            if win.title != title:
                continue
            candidates, boxes = self._scan_window(win, force_refresh=True)
            for cand in candidates:
                if self._handle_one(cand, boxes, win):
                    clicked = True
                    break
        return clicked

    def scan_once(self):
        """返回 (candidates, all_boxes); windows 模式聚合所有 Cursor 窗口。"""
        if self.windows_mode:
            all_candidates = []
            for _win, cands, _boxes in self._detect_windows():
                all_candidates.extend(cands)
            return all_candidates, []
        capture = self.capturer.grab()
        candidates, all_boxes = self.detector.detect(capture)
        return candidates, all_boxes

    def _detect_windows(self):
        from .windows import list_cursor_windows

        def _win_priority(title: str) -> int:
            if title == "Cursor Agents":
                return 0
            if title.endswith(" - Cursor"):
                return 1
            return 2

        results = []
        wins = sorted(list_cursor_windows(), key=lambda w: _win_priority(w.title))
        for win in wins:
            if win.title == "Cursor":
                continue
            unique, all_boxes = self._scan_window(win)
            if unique:
                log.debug("窗口 '%s' 发现 %d 个候选按钮", win.title, len(unique))
            results.append((win, unique, all_boxes))
        if wins:
            titles = [w.title for w in wins if w.title != "Cursor"]
            log.debug("本轮扫描 %d 个窗口(跳过Home): %s", len(titles), titles)
        return results

    @staticmethod
    def _scan_regions(win, img):
        """按窗口类型选择 OCR 区域(右侧 Composer 聊天区, 多段扫描)。"""
        h, w = img.shape[:2]
        if win.title == "Cursor":
            return []
        if win.title == "Cursor Agents":
            x0 = int(w * 0.14)   # Home/会话列表
        elif win.title.endswith(" - Cursor"):
            x0 = int(w * 0.38)   # 项目窗口: 跳过侧栏+编辑器
        else:
            x0 = 0
        panel = img[:, x0:, :]
        ph = panel.shape[0]
        return [
            (panel, 0, x0),
            (panel[int(ph * 0.22) :, :], int(ph * 0.22), x0),
            (panel[int(ph * 0.45) :, :], int(ph * 0.45), x0),
            (panel[int(ph * 0.68) :, :], int(ph * 0.68), x0),
        ]

    def _handle_one(self, cand, all_boxes, win=None) -> bool:
        """对单个候选执行安全判定与点击。返回是否实际点击。"""
        boxes = getattr(cand, "safety_boxes", None) or all_boxes
        decision = self.safety.evaluate(cand, boxes)
        if not decision.allow:
            log.warning("拦截 '%s' @(%d,%d): %s",
                        cand.label, cand.screen_x, cand.screen_y, decision.reason)
            return False
        where = f" @窗口'{win.title}'" if win else ""
        if self.dry_run:
            log.info("[dry-run] 将点击 '%s'%s (%d,%d) score=%.2f",
                     cand.label, where, cand.screen_x, cand.screen_y, cand.box.score)
        else:
            if win is not None:
                from .windows import focus_and_click

                focus_and_click(win.hwnd, cand.screen_x, cand.screen_y,
                                restore_focus=self.cfg.click.restore_focus,
                                restore_mouse=self.cfg.click.restore_mouse)
            else:
                self.clicker.click(cand.screen_x, cand.screen_y)
            self.safety.record_click(cand)
            log.info("点击 '%s'%s (%d,%d) score=%.2f",
                     cand.label, where, cand.screen_x, cand.screen_y, cand.box.score)
        return True

    def step(self) -> None:
        if not self.hotkeys.enabled:
            return
        if self.activity.is_user_active():
            return

        if self.windows_mode:
            for win, candidates, boxes in self._detect_windows():
                for cand in candidates:
                    if self._handle_one(cand, boxes, win):
                        break
            return

        candidates, all_boxes = self.scan_once()
        for cand in candidates:
            if self._handle_one(cand, all_boxes):
                break

    def run(self) -> None:
        self.hotkeys.register()
        wd = self.cfg.watchdog
        log.info("自动确认助手已启动 | 切换: %s | 退出: %s",
                 self.cfg.hotkey.toggle, self.cfg.hotkey.quit)
        log.info("模式=%s, 间隔=%.1fs, dry_run=%s, 巡检=%s/%.0fs",
                 self.cfg.scan.mode, self.cfg.scan.interval_seconds, self.dry_run,
                 "开" if wd.enabled else "关", wd.interval_seconds)
        try:
            while not self.hotkeys.should_quit():
                start = time.monotonic()
                window_results = None
                try:
                    self._log_pause_reasons()
                    if self.windows_mode:
                        window_results = self._detect_windows()
                        if self.hotkeys.enabled and not self.activity.is_user_active():
                            for win, candidates, boxes in window_results:
                                for cand in candidates:
                                    if self._handle_one(cand, boxes, win):
                                        break
                    elif self.hotkeys.enabled and not self.activity.is_user_active():
                        self.step()

                    if wd.enabled and window_results is not None:
                        self.watchdog.run_check(
                            window_results,
                            autopilot_enabled=self.hotkeys.enabled,
                            interval=wd.interval_seconds,
                            retry_on_stuck=wd.retry_on_stuck,
                            orchestrator=self,
                        )
                except Exception:
                    log.exception("主循环单步异常")
                elapsed = time.monotonic() - start
                time.sleep(max(0.0, self.cfg.scan.interval_seconds - elapsed))
        except KeyboardInterrupt:
            log.info("收到 Ctrl+C, 退出")
        log.info("已退出")


def selftest(cfg: AppConfig) -> int:
    print("== 启动自检 ==")
    ok = True
    try:
        cap = ScreenCapturer(monitor=cfg.scan.monitor)
        print(f"[OK] 显示器数量: {cap.monitor_count()}, 监视目标序号: {cfg.scan.monitor}")
        result = cap.grab()
        print(f"[OK] 截屏成功, 尺寸: {result.image.shape}")
    except Exception as e:
        ok = False
        print(f"[FAIL] 截屏失败: {e}")
    try:
        det = ButtonDetector(cfg.detection)
        det._ensure_engine()
        print(f"[OK] OCR 引擎就绪, 目标按钮 {len(cfg.detection.targets)} 个")
    except Exception as e:
        ok = False
        print(f"[FAIL] OCR 引擎初始化失败: {e}")
    print("== 自检通过 ==" if ok else "== 自检存在问题 ==")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursor 自动确认助手")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="只扫描一次并打印候选")
    parser.add_argument("--dry-run", action="store_true", help="检测但不真正点击")
    parser.add_argument("--selftest", action="store_true", help="运行启动自检")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    try:
        from .windows import enable_dpi_awareness
        enable_dpi_awareness()
    except Exception:
        pass

    if args.selftest:
        return selftest(cfg)

    orch = Orchestrator(cfg, dry_run=args.dry_run)

    if args.once:
        candidates, _ = orch.scan_once()
        if not candidates:
            print("未检测到目标按钮。")
        for c in candidates:
            print(f"候选: '{c.label}' @({c.screen_x},{c.screen_y}) "
                  f"score={c.box.score:.2f} text='{c.box.text}'")
        return 0

    lock = SingleInstance()
    if not lock.acquire():
        log.error("检测到已有运行实例(PID=%s), 本次不重复启动。"
                  "如需重启请先退出或运行 stop.bat。", lock.existing_pid())
        return 1
    try:
        orch.run()
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
