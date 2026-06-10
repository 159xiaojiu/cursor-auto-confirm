# Cursor 自动确认助手 (CursorAutoPilot)

自动识别并点击 Cursor Agent 弹出的确认按钮（`Accept` / `Keep` / `Run` / `Continue` / `Resume` 等），减少反复手动点击。内置危险命令拦截与死循环防护。

> 技术规格见 [SPEC.md](SPEC.md)

## 适用场景

- Cursor Agent 频繁弹出确认框，需要人工反复点击
- 希望 Agent 在无人值守时持续推进，同时保留基本安全拦截

## 功能

- **自动点击确认按钮**：识别常见确认文案并自动点击
- **多窗口照看**：可同时处理多个 Cursor 窗口（后台窗口也支持）
- **安全网关**：危险命令拦截、死循环检测、按钮黑白名单
- **托盘控制**：通过系统托盘启动/停止，查看日志

## 工作原理

```
枚举所有 Cursor 窗口 -> 离屏抓取(PrintWindow) -> OCR 识别按钮(RapidOCR)
-> 安全网关(危险命令/死循环) -> 切到该窗口点击 -> 还原原前台窗口
```

扫描模式（`config.yaml` 的 `scan.mode`）：

| 模式 | 说明 |
|------|------|
| `windows`（默认） | 照看所有打开的 Cursor 窗口，含后台窗口 |
| `screen` | 只扫描当前屏幕可见区域，适合单窗口 |

## 快速开始（发布包）

无需安装 Python，使用 `release` 目录中的 zip 包：

1. 解压到任意文件夹（建议使用英文路径）
2. 双击 **`启动.bat`**
3. 可选：双击 **`创建桌面快捷方式.bat`**

包内附带 **`使用说明.txt`**。重新打包请运行 `build_release.bat`。

## 开发环境

需要 Python 3.11+。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -r requirements.txt
```

> 首次运行 OCR 会自动下载模型（约 15MB），需联网。

## 使用

### 托盘模式（推荐）

双击 `launch.bat` 或桌面快捷方式，任务栏右下角出现托盘图标。

右键托盘图标：

- **启动自动点击** — 开始自动处理确认按钮
- **停止自动点击** — 停止自动点击
- **打开日志** — 查看点击记录
- **退出托盘程序** — 关闭程序

托盘图标：**绿色 = 运行中**，**灰色 = 已停止**。

### 命令行

```powershell
.\run.ps1 --selftest    # 启动自检
.\run.ps1 --once        # 扫描一次（不点击）
.\run.ps1 --dry-run     # 检测但不点击
.\start.bat / .\stop.bat # 无托盘时启停后台进程
```

工作进程热键：`Ctrl+Alt+A` 暂停/恢复，`Ctrl+Alt+Q` 退出。

> `keyboard` 全局热键在部分系统需以管理员权限运行终端。

## 配置

在 [config.yaml](config.yaml) 中调整，常用项：

- `scan.mode`：`windows` 或 `screen`
- `scan.interval_seconds`：扫描间隔
- `scan.region`：扫描区域 `[left, top, width, height]`
- `detection.targets`：要自动点击的按钮文案
- `detection.blacklist`：禁止自动点击的按钮（如 `Reject`）
- `safety.dangerous_patterns`：危险命令模式，命中则拦截
- `safety.death_loop`：死循环防护阈值
- `click.restore_focus` / `restore_mouse`：点击后归还焦点与鼠标位置

## 目录结构

```
src/
  main.py       入口 + 主循环
  capture.py    截屏
  detector.py   OCR 按钮检测
  safety.py     安全拦截
  clicker.py    点击执行
  control.py    热键与用户活动检测
  config.py     配置加载
config.yaml
requirements.txt
```

## 安全说明

- 对 `Run` / `Approve` 等命令型按钮会先检查命令文本，命中危险模式即拦截。
- OCR 存在误差，重要环境请先使用 `--dry-run` 观察，勿长时间无人值守。
- 黑名单按钮不会被自动点击。
