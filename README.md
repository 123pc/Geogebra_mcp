# GeoGebra MCP Server

让 Claude Code、Codex 和其他 MCP 客户端直接操控 GeoGebra Classic 6——绘制几何构造、函数图像、3D 图形、动态机构，保存 `.ggb`，导出 `.png`。

> 本项目不是要替代 GeoGebra，而是把 GeoGebra 变成 AI 可以可靠调用的数学可视化后端。

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#配置-ai-客户端">配置客户端</a> ·
  <a href="#mcp-工具">MCP 工具</a> ·
  <a href="#常见问题">常见问题</a> ·
  <a href="#贡献">贡献</a>
</p>

---

## 能做什么

| 场景 | 示例 |
|------|------|
| 函数图像 | `f(x)=sin(x)`, `g(x)=cos(x)`, 交点, 切线 |
| 平面几何 | 三角形, 外接圆, 角平分线, 轨迹, 位似变换 |
| 3D 图形 | 空间曲线, 平面, 球面, 多面体 |
| 机构简图 | 曲柄摇杆, 曲柄滑块, 四连杆, 缩放机构 |
| 数据图表 | 条形图, 直方图, 回归曲线 |
| 动态动画 | 滑块驱动旋转, 轨迹追踪, 自动播放 |

---

## 架构

```text
Claude Code / Codex / DeepSeek TUI / ...
    │
    │  MCP stdio
    ▼
Python MCP Server  (geogebra_mcp/server.py)
    │
    │  subprocess + JSON lines
    ▼
Node.js daemon  (geogebra_mcp/geogebra_daemon.js)
    │
    │  Chrome DevTools Protocol
    ▼
GeoGebra Classic 6  桌面版
```

---

## 环境要求

- **Python 3.10+**
- **Node.js v16+** 和 npm
- **GeoGebra Classic 6** 桌面版（[下载](https://www.geogebra.org/download)）
- 支持 MCP stdio 的 AI 客户端（Claude Code / Codex / …）

Windows、macOS、Linux 均可使用。

---

## 快速开始

### 1. 克隆并安装

```bash
git clone https://github.com/123pc/Geogebra_mcp.git
cd Geogebra_mcp
npm install                  # Node 依赖（puppeteer-core）
python -m pip install -e .   # Python 依赖 + 暴露 CLI 命令
```

> `npm install` 不可省略——Node 守护进程依赖 `puppeteer-core`。  
> 也可运行 `python install_wizard.py` 进行交互式安装向导。

### 2. 环境诊断

```bash
geogebra-mcp-doctor
# 如果命令不在 PATH 中，改用：
python -m geogebra_mcp.doctor
```

预期输出：

```text
[OK] python: 3.13.5
[OK] node: v22.17.1
[OK] npm
[OK] daemon_js: .../geogebra_mcp/geogebra_daemon.js
[OK] package_json: .../geogebra_mcp/package.json
[OK] geogebra_install: .../GeoGebra.exe
[FAIL] cdp_port: localhost:9222
```

`cdp_port` 失败是正常的——下面启动 GeoGebra 即可解决。

### 3. 启动 GeoGebra（调试模式）

每次使用前需要以调试模式启动 GeoGebra：

**Windows：** 双击 `start_geogebra.bat`，或一行命令：
```cmd
for /d %v in ("%LOCALAPPDATA%\GeoGebra_6\app-*") do start "" "%~fv\GeoGebra.exe" --remote-debugging-port=9222
```

**macOS：**
```bash
open -a "GeoGebra Classic 6" --args --remote-debugging-port=9222
```

**Linux：**
```bash
geogebra-classic --remote-debugging-port=9222
```

### 4. 配置 AI 客户端

在你的 MCP 配置文件中加入：

```json
{
  "mcpServers": {
    "geogebra": {
      "command": "geogebra-mcp-server",
      "args": []
    }
  }
}
```

> 如果 `geogebra-mcp-server` 不在 PATH 中，也可以用源码入口：
> ```json
> { "command": "python", "args": ["<仓库路径>/geogebra_mcp_server.py"] }
> ```

Claude Code 用户还需在 `settings.json` 中添加：

```json
{ "enabledMcpjsonServers": ["geogebra"] }
```

重启客户端后生效。

---

## MCP 工具

### 连接与状态

| 工具 | 说明 |
|------|------|
| `geogebra_status` | 检查 GeoGebra 连接状态 |
| `geogebra_version` | 查看 MCP Server 版本 |
| `geogebra_help` | 获取命令/机构/动画参考（`topic="commands"\|"mechanisms"\|"animation"`） |

### 命令执行

| 工具 | 推荐度 | 说明 |
|------|--------|------|
| `geogebra_run_commands` | 推荐 | 结构化数组执行，适合 AI 客户端 |
| `geogebra_create_construction` | 推荐 | 结构化对象执行，带样式和动画 |
| `geogebra_exec` | 备选 | 单条命令执行 |
| `geogebra_batch` | 兼容 | JSON 字符串批量执行，兼容旧客户端 |
| `geogebra_draw_mechanism` | 兼容 | JSON 字符串机构绘制，兼容旧客户端 |

### 视图与外观

| 工具 | 说明 |
|------|------|
| `geogebra_new_construction` | 清空当前构造 |
| `geogebra_set_view` | 设置视图：`G`（几何）、`AG`（代数+几何）、`3D`、`T`（表格） |
| `geogebra_set_appearance` | 颜色、线宽、点大小、标签可见性 |
| `geogebra_animate` | 启动/停止滑块动画，设置速度 |
| `geogebra_get_objects` | 获取当前构造对象列表（用于自验收） |

### 输出

| 工具 | 说明 |
|------|------|
| `geogebra_save` | 保存为 `.ggb` 文件 |
| `geogebra_export_png` | 导出当前视图为 `.png` |

---

## 给 AI 的调用流程

AI 在处理绘图请求时应遵循以下步骤：

1. **确认输出路径** — 如果用户没指定保存位置，先问「文件保存在哪里？」
2. **检查连接** — `geogebra_status`
3. **未连接时提示** — 告知用户双击 `start_geogebra.bat` 启动 GeoGebra
4. **设置视图** — `geogebra_set_view`
5. **清空画布**（如需） — `geogebra_new_construction`
6. **发送命令** — 用 `geogebra_run_commands` 或 `geogebra_create_construction`
7. **自验收** — `geogebra_get_objects`，确认对象数 >= 3
8. **动画**（如需） — `geogebra_set_appearance` 使滑块可见 + `geogebra_animate` 自动播放
9. **保存** — `geogebra_save`

---

## 示例

### 用自然语言

> "画 y=sin(x) 和 y=cos(x)，标出交点，导出到 D:/output/sin_cos.png"

### 曲柄摇杆机构

```json
{
  "name": "crank_rocker",
  "design": {
    "perspective": "G",
    "commands": [
      "O1=(0,0)", "O2=(6,0)", "alpha=30 deg",
      "A=O1+(2*cos(alpha),2*sin(alpha))",
      "c1=Circle(A,5)", "c2=Circle(O2,4)",
      "B=Intersect(c1,c2,1)",
      "crank=Segment(O1,A)", "coupler=Segment(A,B)",
      "rocker=Segment(B,O2)", "ground=Segment(O1,O2)"
    ],
    "styles": [
      {"label":"crank","color":[1,0,0],"thickness":6},
      {"label":"coupler","color":[0,0.2,1],"thickness":6},
      {"label":"rocker","color":[0,0.7,0.2],"thickness":6},
      {"label":"ground","color":[0,0,0],"thickness":5}
    ],
    "animate": "alpha",
    "speed": 0.5
  },
  "output_dir": "D:/output"
}
```

> 推荐使用 ASCII 标签（`alpha` 而非 `α`），避免不同客户端间的编码问题。

---

## Skills

仓库附带两套 skill，可教 AI 更稳定地使用本 MCP：

| Skill | 用途 |
|-------|------|
| `skills/geogebra-master` | 教 AI 像 GeoGebra 专家一样作图——强制滑块可见、自动播放动画、自验收 |
| `skills/use-geogebra-mcp` | 教 AI 部署、配置和诊断本 MCP |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GEOGEBRA_CDP_PORT` | `9222` | GeoGebra 远程调试端口 |

---

## 常见问题

### `connected: false`

GeoGebra 未以调试模式运行。确保已用 `--remote-debugging-port=9222` 启动（见[快速开始](#快速开始)第 3 步）。

### 动画不动

检查三点：
1. 是否创建了角度滑块（`alpha=30 deg`）
2. 运动点是否依赖滑块（`A=O+(2*cos(alpha),2*sin(alpha))`）
3. 是否调用了 `geogebra_set_appearance` 使滑块**可见** + `geogebra_animate(label="alpha", animate=true)`

### AI 画的图和实际不符 / 空白

让 AI 调用 `geogebra_get_objects` 自验收。如果对象数为 0，AI 应重试而非声称"完成"。

### 已经打开的 GeoGebra 能接管吗？

不能。必须关闭后以 `--remote-debugging-port=9222` 重新启动。

### 能在 macOS / Linux 上用吗？

可以。三平台均已适配。

### 为什么要用 `alpha` 而非 `α`？

希腊字母在部分客户端、终端或 JSON 日志中可能出现编码异常。推荐默认使用 ASCII 名称以提高普适性。

---

## 开发

```bash
# 运行测试
python -m pytest -q                     # Python (47 tests)
node tests/test_daemon_protocol.js      # Node (12 tests)

# 构建 wheel
python -m build --wheel
```

---

## 贡献

欢迎所有形式的贡献！

- 在 [Issues](https://github.com/123pc/Geogebra_mcp/issues) 中报告 bug 或提出功能建议
- 提交 Pull Request 改进代码、文档或 skill
- 测试并适配更多 AI 客户端（Codex、DeepSeek TUI 等）
- 分享你用它绘制的有趣构造

### 当前适配状态

| 客户端 | 状态 |
|--------|------|
| Claude Code | 已测试 |
| Codex | 适配中 |
| DeepSeek TUI | 计划中 |
| 其他 MCP 客户端 | 欢迎测试反馈 |

---

## 许可证

MIT © 2026 [GeoGebra MCP contributors](https://github.com/123pc/Geogebra_mcp/graphs/contributors)
