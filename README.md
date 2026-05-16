# GeoGebra MCP Server

通过 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 让 Claude Code 直接操控 [GeoGebra Classic 6](https://www.geogebra.org/)，绘制机构运动简图、几何构造并导出 `.ggb` 文件。

## 效果

在 Claude Code 中说「画一个曲柄摇杆机构」，GeoGebra 窗口中就会出现带实时动画的机构模型，同时自动保存 `.ggb` 文件。

## 工作原理

```
Claude Code ── stdio ── Python MCP Server ── subprocess ── Node.js Daemon ── CDP/WebSocket ── GeoGebra Classic 6
```

- **Python MCP Server**：实现 MCP 协议，注册工具，与 Claude Code 通信
- **Node.js Daemon**：通过 [Puppeteer](https://pptr.dev/) 连接 GeoGebra 的 Chrome DevTools Protocol 端口，调用 `ggbApplet` API
- **GeoGebra Classic 6**：基于 Electron 的桌面应用，启动时开启 `--remote-debugging-port` 即可被外部操控

## 前置依赖

- **Windows**（GeoGebra Classic 6 桌面版目前仅支持 Windows 路径；macOS/Linux 可自行调整启动方式）
- [Node.js](https://nodejs.org/) v16+
- [Python](https://www.python.org/) 3.10+
- [GeoGebra Classic 6](https://www.geogebra.org/download) 已安装

## 安装

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd Geogebra_mcp

# 2. 安装 Node.js 依赖
npm install

# 3. 安装 Python 依赖
pip install mcp
```

## 启动 GeoGebra

每次使用前，以调试模式启动 GeoGebra：

**Windows（快捷方式）：**
```
"C:\Users\<用户名>\AppData\Local\GeoGebra_6\app-<版本号>\GeoGebra.exe" --remote-debugging-port=9222
```

> 提示：可将此行保存为 `start_geogebra.bat`，双击启动。GeoGebra 版本号在安装目录下查看，如 `app-6.0.8890`。

## 配置 Claude Code

在 `~/.claude/` 目录下创建/修改两个文件：

**① `.mcp.json`**（注册 MCP Server）：

```json
{
  "mcpServers": {
    "geogebra": {
      "command": "python",
      "args": ["<本仓库路径>/geogebra_mcp_server.py"]
    }
  }
}
```

**② `settings.json`**（允许 MCP Server 自动运行）。在已有配置基础上添加：

```json
"enabledMcpjsonServers": ["geogebra"]
```

完成后重启 Claude Code 即可生效。

## 可用的 MCP 工具

| 工具 | 说明 |
|------|------|
| `geogebra_exec` | 执行单条 GeoGebra 命令 |
| `geogebra_batch` | 批量执行命令 |
| `geogebra_new_construction` | 清空当前构造 |
| `geogebra_save` | 保存为 `.ggb` 文件 |
| `geogebra_export_png` | 导出 PNG 截图 |
| `geogebra_status` | 查看连接状态 |
| `geogebra_set_view` | 切换视图（几何/代数/3D） |
| `geogebra_set_appearance` | 设置颜色、线宽、点大小、可见性 |
| `geogebra_animate` | 控制动画播放/停止 |
| `geogebra_get_objects` | 列出当前构造中的所有对象 |
| `geogebra_draw_mechanism` | 一站式机构绘制（新建 → 命令 → 样式 → 保存） |

## 使用示例

在 Claude Code 中直接对话即可：

> "画一个曲柄摇杆机构，机架间距 6，曲柄长 2，连杆长 5，摇杆长 4，带旋转动画，保存到 D:/output/crank_rocker.ggb"

Claude 会自动调用 `geogebra_draw_mechanism` 工具完成。你也可以手动构造 JSON 调用：

```json
{
  "name": "crank_rocker",
  "design_json": "{
    \"perspective\": \"G\",
    \"animate\": \"α\",
    \"speed\": 0.5,
    \"commands\": [
      \"O1 = (0, 0)\",
      \"O2 = (6, 0)\",
      \"α = 45°\",
      \"A = O1 + (2*cos(α), 2*sin(α))\",
      \"c1 = Circle(A, 5)\",
      \"c2 = Circle(O2, 4)\",
      \"B = Intersect(c1, c2, 1)\",
      \"Segment(O1, A)\",
      \"Segment(A, B)\",
      \"Segment(B, O2)\"
    ],
    \"styles\": [
      {\"label\": \"A\", \"color\": [1,0,0], \"point_size\": 5},
      {\"label\": \"B\", \"color\": [0,0,1], \"point_size\": 5}
    ]
  }"
}
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `geogebra_mcp_server.py` | **主入口** — MCP Server，Claude Code 通过它调用 GeoGebra |
| `geogebra_daemon.js` | **守护进程** — 维持与 GeoGebra 的 CDP 长连接 |
| `geogebra_bridge.js` | 独立桥接器（可脱离 MCP 直接命令行使用） |
| `geogebra_api.py` | Python 封装（可脱离 MCP 在脚本中使用） |
| `geogebra_bridge.py` | 纯 Python CDP 连接（备用方案） |

## 常见问题

**Q: Claude Code 提示连接失败？**
A: 确保 GeoGebra 已以 `--remote-debugging-port=9222` 参数启动，且端口未被占用。

**Q: 动画不播放？**
A: GeoGebra 窗口需要保持打开且可见。最小化时 Electron 可能暂停渲染。

**Q: 能在 macOS/Linux 上使用吗？**
A: 原理可行，需要调整 GeoGebra 启动路径和 CDP 连接方式。欢迎 PR。

## 许可

MIT
