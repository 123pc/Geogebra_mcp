# GeoGebra MCP Server

GeoGebra MCP Server 让 Claude Code、Codex 和其他支持 MCP 的 AI 工具直接控制 GeoGebra Classic 6：绘制函数图像、几何构造、3D 图形、动态机构、保存 `.ggb` 文件，并导出 PNG 截图。

本项目的目标不是替代 GeoGebra，而是把 GeoGebra 变成 AI 可以可靠调用的绘图和数学构造后端。

## 能做什么

- 让 AI 在 GeoGebra 中执行命令，例如创建点、线、圆、函数、交点、滑块和动画。
- 绘制曲柄摇杆、曲柄滑块、四连杆等机构简图。
- 构造平面几何、函数图像、3D 对象、数据图表和概率演示。
- 通过 Chrome DevTools Protocol 连接到 GeoGebra Classic 6 桌面窗口。
- 保存当前构造为 `.ggb`，导出当前视图为 `.png`。
- 通过 skills 指导 Claude Code/Codex 更稳定地使用本 MCP。

GeoGebra 使用范式参考了官方 Tutorials 页面中的分类：Getting Started、Graphing、Geometry、3D Graphics、CAS、Spreadsheet、Probability 和 Advanced Tutorials。

## 架构

```text
Claude Code / Codex
        |
        | MCP stdio
        v
Python MCP Server
        |
        | subprocess + JSON lines
        v
Node.js daemon
        |
        | CDP / WebSocket
        v
GeoGebra Classic 6 desktop app
```

核心组件：

| 文件/模块 | 作用 |
| --- | --- |
| `geogebra_mcp/server.py` | MCP Server 主入口，注册 GeoGebra 工具 |
| `geogebra_mcp/geogebra_daemon.js` | Node.js 守护进程，通过 CDP 调用 `ggbApplet` |
| `geogebra_mcp/auto_launcher.py` | 跨平台查找并自动启动 GeoGebra Classic 6 |
| `geogebra_mcp/doctor.py` | 环境诊断命令 |
| `geogebra_mcp_server.py` | 源码运行兼容入口 |
| `install_wizard.py` | 交互式安装/配置向导 |
| `skills/use-geogebra-mcp` | 面向部署和基本使用流程的 skill |
| `skills/geogebra-master` | 面向 GeoGebra 专家作图策略的 skill |

## 环境要求

- Python 3.10 或更高版本
- Node.js 和 npm
- GeoGebra Classic 6 桌面版
- Claude Code、Codex 或其他支持 MCP stdio 的客户端

Windows、macOS、Linux 都可以使用，但自动查找 GeoGebra 的路径依赖本机安装方式。如果诊断失败，请先确认 GeoGebra Classic 6 已安装。

## 从源码安装

```bash
git clone https://github.com/123pc/Geogebra_mcp.git
cd Geogebra_mcp
npm install
python -m pip install -e .
```

说明：

- `npm install` 是必须的，因为 Node 守护进程依赖 `puppeteer-core`。
- `python -m pip install -e .` 会安装 Python MCP server，并暴露命令 `geogebra-mcp-server` 和 `geogebra-mcp-doctor`。
- 如果你只想快速试用，也可以运行 `python install_wizard.py`，按提示完成环境检查和配置。

## 环境诊断

安装后运行：

```bash
geogebra-mcp-doctor
```

你会看到类似检查项：

```text
[OK] python
[OK] node
[OK] npm
[OK] daemon_js
[OK] package_json
[OK] geogebra_install
[FAIL] cdp_port: localhost:9222
```

`cdp_port` 失败表示 GeoGebra 当前没有以调试模式运行。请双击 `start_geogebra.bat` 或按命令行动手动启动 GeoGebra Classic 6。

如果 `node`、`npm`、`daemon_js`、`package_json` 或 `geogebra_install` 失败，需要先修复对应环境问题。

## 配置 Claude Code / Codex

推荐使用安装后的命令形式：

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

如果你在源码目录中直接运行，也可以使用兼容入口：

```json
{
  "mcpServers": {
    "geogebra": {
      "command": "python",
      "args": ["D:/project/Geogebra_mcp/geogebra_mcp_server.py"]
    }
  }
}
```

Claude Code 如果启用了 MCP allowlist，还需要在设置中允许该 server：

```json
{
  "enabledMcpjsonServers": ["geogebra"]
}
```

不同客户端的配置文件位置可能不同。重点是三件事：

1. server 名称建议固定为 `geogebra`。
2. command 指向 `geogebra-mcp-server` 或源码入口。
3. 客户端需要允许这个 MCP server 被调用。

## 启动 GeoGebra（必须手动）

**当前版本需要用户手动启动 GeoGebra Classic 6 并开启远程调试端口。** 自动启动功能在代码中已实现，但在部分 Windows 环境下还不够稳定。

### 每次使用前

以调试模式启动 GeoGebra Classic 6：

**Windows：** 双击项目目录下的 `start_geogebra.bat`，或执行：
```cmd
"%LOCALAPPDATA%\GeoGebra_6\app-<版本号>\GeoGebra.exe" --remote-debugging-port=9222
```

**macOS：**
```bash
open -a "GeoGebra Classic 6" --args --remote-debugging-port=9222
```

**Linux：**
```bash
geogebra-classic --remote-debugging-port=9222
```

GeoGebra 窗口出现后，MCP Server 会自动连接。可以在 Claude Code 中直接开始使用。

> 运行 `python install_wizard.py` 可自动生成平台对应的一键启动脚本。

### 环境变量

| 变量 | 作用 |
| --- | --- |
| `GEOGEBRA_CDP_PORT=9222` | 修改 CDP 调试端口 |

## MCP 工具

| 工具 | 用途 |
| --- | --- |
| `geogebra_status` | 检查连接状态 |
| `geogebra_help` | 查看命令、机构、动画帮助 |
| `geogebra_version` | 查看 server 版本 |
| `geogebra_new_construction` | 清空当前构造 |
| `geogebra_exec` | 执行单条 GeoGebra 命令 |
| `geogebra_batch` | 用 JSON 字符串批量执行命令，兼容旧客户端 |
| `geogebra_run_commands` | 用结构化数组批量执行命令，推荐 AI 客户端使用 |
| `geogebra_create_construction` | 用结构化 design 对象创建完整构造，推荐用于复杂作图 |
| `geogebra_draw_mechanism` | 用 JSON 字符串创建机构图，兼容旧客户端 |
| `geogebra_set_view` | 设置视图，例如 `G`、`AG`、`3D`、`T` |
| `geogebra_set_appearance` | 设置颜色、线宽、点大小、标签可见性 |
| `geogebra_animate` | 启动或停止滑块动画 |
| `geogebra_get_objects` | 获取当前构造对象列表 |
| `geogebra_save` | 保存 `.ggb` 文件 |
| `geogebra_export_png` | 导出 PNG 截图 |

## 推荐给 AI 的调用流程

AI 不应该上来就画图。推荐流程是：

1. 如果用户没有指定输出路径，先问用户「文件保存在哪里」。
2. 调用 `geogebra_status` 检查连接。
3. 如果未连接，提示用户用 `start_geogebra.bat` 或命令行启动 GeoGebra。
4. 根据任务类型选择视图：函数和几何用 `G` 或 `AG`，3D 用 `3D`，表格数据用 `T`。
5. 如果是新图，调用 `geogebra_new_construction`。
6. 用 `geogebra_run_commands` 或 `geogebra_create_construction` 创建对象。
7. 用 `geogebra_get_objects` 验证对象是否创建成功。
8. 如有需要，调用 `geogebra_animate`、`geogebra_save`、`geogebra_export_png`。

## 直接使用示例

### 画函数图像

用户可以对 Claude Code/Codex 说：

```text
用 GeoGebra 画 y=sin(x) 和 y=cos(x)，标出它们的一个交点，并导出 PNG。
```

AI 应该调用类似命令：

```json
{
  "commands": [
    "f(x)=sin(x)",
    "g(x)=cos(x)",
    "A=Intersect(f,g,1)",
    "t=Tangent(A,f)"
  ]
}
```

### 构造三角形外接圆

```json
{
  "commands": [
    "A=(0,0)",
    "B=(5,0)",
    "C=(1.5,3)",
    "tri=Polygon(A,B,C)",
    "cc=Circle(A,B,C)"
  ]
}
```

### 创建曲柄摇杆机构

建议使用 ASCII 标签，避免不同客户端对希腊字母编码不一致：

```json
{
  "name": "crank_rocker",
  "design": {
    "perspective": "G",
    "animate": "alpha",
    "speed": 0.5,
    "commands": [
      "O1=(0,0)",
      "O2=(6,0)",
      "alpha=45 deg",
      "A=O1+(2*cos(alpha),2*sin(alpha))",
      "c1=Circle(A,5)",
      "c2=Circle(O2,4)",
      "B=Intersect(c1,c2,1)",
      "ground=Segment(O1,O2)",
      "crank=Segment(O1,A)",
      "coupler=Segment(A,B)",
      "rocker=Segment(B,O2)"
    ],
    "styles": [
      {"label": "ground", "color": [0, 0, 0], "thickness": 5},
      {"label": "crank", "color": [1, 0, 0], "thickness": 6},
      {"label": "coupler", "color": [0, 0.2, 1], "thickness": 6},
      {"label": "rocker", "color": [0, 0.7, 0.2], "thickness": 6},
      {"label": "A", "point_size": 5},
      {"label": "B", "point_size": 5}
    ]
  },
  "output_dir": "D:/project/Geogebra_mcp/output"
}
```

## Skills

仓库内提供两套 skill：

| Skill | 适用场景 |
| --- | --- |
| `skills/use-geogebra-mcp` | 教 AI 如何部署、配置、诊断和调用本 MCP |
| `skills/geogebra-master` | 教 AI 像 GeoGebra 熟练用户一样规划作图、选择命令、构造动画并验证结果 |

推荐给 Claude Code/Codex 的用户提示：

```text
使用 use-geogebra-mcp 配置并检查 GeoGebra MCP，然后使用 geogebra-master 在 GeoGebra 中绘制一个曲柄摇杆机构。
```

如果你的客户端支持本地 skills，将这两个目录放到客户端可发现的 skills 目录中；如果客户端只能读取项目内 skill，则让 AI 显式读取本仓库 `skills/` 下的对应目录。

## 常见问题

### Claude Code 显示 `connected: false`

GeoGebra 没有以调试模式运行。请手动启动：

**Windows：** 双击 `start_geogebra.bat`，或执行：
```cmd
"%LOCALAPPDATA%\GeoGebra_6\app-<版本号>\GeoGebra.exe" --remote-debugging-port=9222
```

如果仍然失败，运行诊断：

```bash
geogebra-mcp-doctor
```

常见原因：
- GeoGebra Classic 6 没有安装。
- `--remote-debugging-port=9222` 参数没加上（直接双击桌面图标打开的 GeoGebra 不带调试端口）。
- 端口 `9222` 被占用。
- Node.js/npm 没安装，或没有运行 `npm install`。

### 已经打开的 GeoGebra 能直接接管吗？

不能。必须关闭后用 `--remote-debugging-port=9222` 重新启动。

### 安装 wheel 后 Node 依赖还需要吗？

需要。wheel 会包含 daemon 的 JavaScript 文件和 `package.json`，但不会把 `node_modules` 打进 Python 包。请在项目目录或部署目录执行 `npm install`。

### 为什么建议用 `alpha` 而不是 `α`？

GeoGebra 支持希腊字母，但不同 AI 客户端、终端、JSON 和日志链路可能出现编码问题。为了让构造更普适，推荐默认使用 ASCII 名称，例如 `alpha`、`beta`、`theta`。

### 动画不动怎么办？

检查三点：

1. 是否创建了真正的滑块，例如 `alpha=45 deg`。
2. 运动点是否依赖滑块，例如 `A=O+(2*cos(alpha),2*sin(alpha))`。
3. 是否调用了 `geogebra_animate(label="alpha", animate=true, speed=0.5)`。

## 开发与验证

运行 Python 测试：

```bash
python -m pytest -q
```

运行 Node 协议测试：

```bash
node tests/test_daemon_protocol.js
```

构建 wheel：

```bash
python -m build --wheel
```

验证 skills：

```bash
python C:/Users/35148/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/use-geogebra-mcp
python C:/Users/35148/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/geogebra-master
```

## 许可证

MIT
