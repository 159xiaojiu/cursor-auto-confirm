# Cursor 自动确认助手 (CursorAutoPilot)

自动识别并点击 Cursor 弹出的确认类按钮（`Accept` / `Keep` / `Run` / `Continue` / `Resume` 等），
让 Agent 在无人值守时也能持续推进，省去反复手动点击。内置危险命令拦截与死循环防护。

> 技术规格见 [SPEC.md](SPEC.md)。当前为 v0.1（OCR 检测路线）。

## 产品亮点（作品集视角）

- **从真实工作流出发**：解决 Cursor Agent 频繁卡在确认弹窗、无法无人值守推进的痛点
- **安全网关设计**：危险命令拦截、死循环检测、按钮黑白名单，平衡自动化与可控性
- **多窗口照看**：后台离屏识别所有 Cursor 窗口，适配多项目并行场景
- **可交付形态**：托盘小助手 + 免安装 zip 发布包，降低分享与使用门槛

## 工作原理

```
枚举所有 Cursor 窗口 -> 逐个离屏抓取(PrintWindow) -> OCR 识别按钮文字(RapidOCR)
-> 安全网关(危险命令/死循环) -> 切到该窗口点击 -> 还原原前台窗口
```

支持两种扫描模式(`config.yaml` 的 `scan.mode`)：

- `windows`(默认, 推荐)：**同时照看所有打开的 Cursor 窗口**，即使某个窗口在后台/被其他窗口遮挡，也能离屏识别它的按钮并点击。多个项目同时跑时，每个窗口的确认都会被处理。
- `screen`：只扫当前屏幕可见画面(单窗口场景)。

即使你切到其他 App、Cursor 不在前台，工具仍会识别并点击弹出的按钮。

## 分享给他人（推荐）

已打好**免安装发布包**，直接发 zip 即可，对方无需装 Python：

```
release\Cursor自动确认助手_Win64.zip
```

对方操作：
1. 解压到任意文件夹（建议英文路径）
2. 双击 **`启动.bat`**
3. 可选：双击 **`创建桌面快捷方式.bat`** 放到桌面

文件夹内自带 **`使用说明.txt`**。

重新打包（开发者）：双击 `build_release.bat`。

---

## 开发环境安装

需要 Python 3.11+（推荐 3.13）。

> 注意：本项目目录名为中文 `自动点击`，新版 pip 在中文路径下创建的虚拟环境会触发证书 bug，
> 因此**虚拟环境建在英文路径** `C:\Users\23986\autopilot_venv`（代码仍留在本目录，互不影响）。

```powershell
# 创建英文路径的虚拟环境
py -3.13 -m venv C:\Users\23986\autopilot_venv
# 预装构建工具(避免源码包构建时再次联网拉取)
C:\Users\23986\autopilot_venv\Scripts\python.exe -m pip install setuptools wheel
# 安装依赖
C:\Users\23986\autopilot_venv\Scripts\python.exe -m pip install --no-build-isolation -r requirements.txt
```

> 首次运行 OCR 会自动下载模型（约 15MB），需联网。

## 使用（推荐：桌面托盘小助手）

桌面上已创建快捷方式 **`Cursor自动确认`**（也可双击项目里的 `launch.bat`）。

1. **双击桌面图标** → 任务栏右下角出现圆形托盘图标
2. **右键托盘图标**：
   - **启动自动点击** — 开始帮你点 Accept / Run / Continue（照看所有 Cursor 窗口）
   - **停止自动点击** — 完全停掉，不再点击
   - **打开日志** — 查看点击记录
   - **退出托盘程序** — 关闭小助手本身（会先停掉自动点击）

托盘图标颜色：**绿色 = 运行中**，**灰色 = 已停止**。

> 托盘程序可一直开着；需要时点「启动」，不需要时点「停止」即可。

### 命令行（调试用）

```powershell
.\run.ps1 --selftest    # 启动自检
.\run.ps1 --once        # 扫描一次（不点击）
.\run.ps1 --dry-run     # 检测但不点击
.\start.bat / .\stop.bat # 无托盘时直接启停后台进程
```

工作进程运行时也可用热键：`Ctrl+Alt+A` 暂停/恢复，`Ctrl+Alt+Q` 退出工作进程。

> 提示：`keyboard` 库注册全局热键在部分系统需以管理员权限运行 PowerShell。

## 配置

所有行为在 [config.yaml](config.yaml) 中调整，常用项：

- `scan.mode`：`windows`=多窗口离屏照看（默认）；`screen`=只扫可见屏幕。
- `scan.monitor`：[screen 模式] 监视哪块显示器（`0`=全部拼合，`1`=主屏，`2`=第二块...）。
- `scan.interval_seconds`：扫描间隔，越小越灵敏、越费 CPU。
- `scan.region`：限定扫描区域 `[left, top, width, height]`，缩小范围可大幅提速。
- `detection.targets`：要自动点击的按钮文案（更具体的放前面）。
- `detection.blacklist`：绝不点击的按钮（如 `Add to Allowlist` / `Reject` / `Undo`）。
- `safety.dangerous_patterns`：危险命令模式，命中则拦截 `Run`/`Approve`。
- `safety.death_loop`：死循环防护阈值与冷却时长。
- `click.restore_focus` / `restore_mouse`：点击后归还焦点 / 还原鼠标位置。
- `click.pause_on_user_activity_seconds`：检测到你在操作时暂停点击。

## 目录结构

```
src/
  main.py       入口 + Orchestrator 主循环
  capture.py    截屏
  detector.py   OCR 按钮检测
  safety.py     危险命令拦截 + 死循环检测
  clicker.py    点击 + 失焦归还
  control.py    热键 + 用户活动检测
  config.py     配置加载
config.yaml     配置
requirements.txt
```

## 安全说明

- 默认对 `Run` / `Approve` 等命令型按钮会先读取上方命令文本，命中危险模式（`rm -rf`、`format`、管道执行等）即拦截。
- OCR 识别有误差，**请勿在涉及重要数据/生产环境时无人值守长时间运行**；建议先用 `--dry-run` 观察。
- 黑名单按钮（如 `Add to Allowlist`）绝不会被自动点击。
