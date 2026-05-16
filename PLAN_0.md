# PLAN_0 — GeoGebra MCP 公开发布路线图

## 已完成

- [x] 核心 MCP 工具（11 个）
- [x] 跨平台自动查找 & 启动 GeoGebra
- [x] 一键安装脚本 `setup.py`
- [x] pip 可安装 `pyproject.toml`
- [x] Docker 容器化
- [x] README 文档
- [x] CDP 端口可配置 `GEOGEBRA_CDP_PORT`

---

## 第一阶段：必须（发布前硬门槛）

### 1.1 搭建测试框架
- [ ] 创建 `tests/` 目录，安装 `pytest` + `pytest-asyncio`
- [ ] `auto_launcher.py` 单元测试（路径扫描逻辑 mock `glob.glob`）
- [ ] `geogebra_daemon.js` 最小测试（JSON 行协议解析）
- [ ] `geogebra_mcp_server.py` 工具调用 mock 测试
- [ ] 覆盖率目标 80%

### 1.2 守护进程自动重连
- [ ] 守护进程崩溃后 MCP Server 自动重启 daemon 并重连
- [ ] 工具调用过程中 daemon 断开 → 自动重试一次再报错

### 1.3 添加 LICENSE 文件
- [ ] 根目录创建 `LICENSE`（MIT）

### 1.4 错误信息国际化
- [ ] `geogebra_mcp_server.py` 和 `auto_launcher.py` 的 stderr 输出中英双语
- [ ] 工具返回的错误 JSON 中 `error` 字段使用英文

---

## 第二阶段：建议（首批用户后）

### 2.1 CI/CD
- [ ] GitHub Actions：push 自动跑 pytest
- [ ] GitHub Actions：push 自动跑 ESLint（检查 .js 文件）
- [ ] 打 tag `v*.*.*` 时自动发布到 PyPI

### 2.2 版本管理
- [ ] `geogebra_mcp_server.py` 内定义 `__version__`
- [ ] 创建 `CHANGELOG.md`
- [ ] 遵循语义化版本（Semantic Versioning）

### 2.3 依赖锁定
- [ ] 明确 `mcp` 的最低兼容版本（而不是 `>=1.0.0` 一刀切）
- [ ] `puppeteer-core` vs GeoGebra Chromium 版本兼容表

---

## 第三阶段：锦上添花（增长期）

### 3.1 零门槛体验
- [ ] `setup.py` 支持自动下载 GeoGebra Classic 6（若未安装）
- [ ] 提供 `.ggb` 模板库（曲柄摇杆、四连杆、凸轮等常见机构）

### 3.2 演示 & 推广
- [ ] 录制使用视频/GIF
- [ ] 发布到 Smithery.ai（容器模式）
- [ ] 发布到 npm（`npx geogebra-mcp`）

### 3.3 社区
- [ ] Issue 模板（Bug Report / Feature Request）
- [ ] 贡献指南 `CONTRIBUTING.md`

---

## 当前进度

- 第一阶段：0 / 4
- 第二阶段：0 / 3
- 第三阶段：0 / 3

## 下次工作

从 **1.1 搭建测试框架** 开始。

---

> 执行时按顺序逐阶段推进，每完成一项标记 `[x]`。
