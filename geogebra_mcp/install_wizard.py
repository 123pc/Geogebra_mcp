"""
GeoGebra MCP Server — 一键安装 & 配置向导
纯标准库，无需预装依赖即可运行: python install_wizard.py
"""

import os
import sys
import subprocess
import shutil
import json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── 工具函数 ──

def check_cmd(name, *args):
    """检查命令是否存在并返回版本信息"""
    exe = shutil.which(name)
    if not exe:
        return None, ""
    try:
        result = subprocess.run([name, *args], capture_output=True, text=True, timeout=10)
        return exe, result.stdout.strip() or result.stderr.strip()
    except Exception:
        return exe, "(found but could not run)"


def section(title):
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")


def ask(question, default="Y"):
    """询问 Y/n，回车默认 Yes"""
    hint = " [Y/n]" if default == "Y" else " [y/N]"
    try:
        ans = input(f"  {question}{hint} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  已取消。")
        sys.exit(0)
    if not ans:
        ans = default.lower()
    return ans in ("y", "yes")


# ── 各步骤 ──

def step_check_env():
    section("第 1 步：检查环境")

    python_exe, python_ver = check_cmd("python", "--version")
    node_exe, node_ver = check_cmd("node", "--version")
    npm_exe, npm_ver = check_cmd("npm", "--version")

    ok = True
    if python_exe:
        print(f"  [OK] Python:  {python_exe}  →  {python_ver}")
    else:
        print("  [!!] Python 未找到，请安装 Python 3.10+")
        ok = False

    if node_exe:
        print(f"  [OK] Node.js: {node_exe}  →  {node_ver}")
    else:
        print("  [!!] Node.js 未找到，请安装 Node.js v16+")
        ok = False

    if npm_exe:
        print(f"  [OK] npm:      {npm_ver}")
    elif node_exe:
        print("  [!!] npm 未找到（通常随 Node.js 一同安装）")

    return ok


def step_install_python_deps():
    section("第 2 步：安装 Python 依赖")
    req_file = os.path.join(PROJECT_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        print("  [!!] 未找到 requirements.txt")
        return False
    print(f"  pip install -r requirements.txt")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        cwd=PROJECT_DIR,
    )
    ok = result.returncode == 0
    print("  [OK] 完成" if ok else "  [!!] 安装失败，请检查 pip")
    return ok


def step_install_node_deps():
    section("第 3 步：安装 Node.js 依赖")
    print(f"  npm install (目录: {PROJECT_DIR})")
    result = subprocess.run(["npm", "install"], cwd=PROJECT_DIR)
    ok = result.returncode == 0
    print("  [OK] 完成" if ok else "  [!!] npm install 失败")
    return ok


def step_find_geogebra():
    section("第 4 步：查找 GeoGebra Classic 6")

    try:
        from auto_launcher import find_geogebra_installation
        path = find_geogebra_installation()
    except Exception:
        path = None

    if path:
        print(f"  [OK] 找到: {path}")
    else:
        print("  [--] 未自动检测到 GeoGebra Classic 6 安装")
        print("       下载地址: https://www.geogebra.org/download")
    return path


def step_create_launcher(geogebra_path):
    section("第 5 步：创建 GeoGebra 启动器")

    system = sys.platform
    if not geogebra_path:
        print("  跳过（未找到 GeoGebra 安装）")
        if system == "win32":
            print('  请手动以调试模式启动:  GeoGebra.exe --remote-debugging-port=9222')
        elif system == "darwin":
            print("  请手动以调试模式启动:  open -a 'GeoGebra Classic 6' --args --remote-debugging-port=9222")
        else:
            print("  请手动以调试模式启动:  geogebra-classic --remote-debugging-port=9222")
        return

    if system == "win32":
        script = os.path.join(PROJECT_DIR, "start_geogebra.bat")
        content = f'@echo off\r\nstart "" "{geogebra_path}" --remote-debugging-port=9222\r\n'
    elif system == "darwin":
        script = os.path.join(PROJECT_DIR, "start_geogebra.command")
        content = f'#!/bin/bash\nopen -a "GeoGebra Classic 6" --args --remote-debugging-port=9222\n'
    else:
        script = os.path.join(PROJECT_DIR, "start_geogebra.sh")
        content = f'#!/bin/bash\n"{geogebra_path}" --remote-debugging-port=9222 &\n'

    with open(script, "w", encoding="utf-8") as f:
        f.write(content)
    if system != "win32":
        os.chmod(script, 0o755)
    print(f"  [OK] 已创建: {script}")


def step_generate_mcp_config():
    section("第 6 步：Claude Code MCP 配置")

    mcp_config = {
        "mcpServers": {
            "geogebra": {
                "command": "python",
                "args": [os.path.join(PROJECT_DIR, "geogebra_mcp_server.py")],
            }
        }
    }

    mcp_json = json.dumps(mcp_config, indent=2, ensure_ascii=False)
    print("  将以下内容添加到 ~/.claude/.mcp.json（如文件已存在则合并 mcpServers）：\n")
    print(mcp_json)

    target = os.path.expanduser("~/.claude/.mcp.json")
    if ask("是否自动写入 ~/.claude/.mcp.json？"):
        try:
            existing = {}
            if os.path.exists(target):
                with open(target, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.setdefault("mcpServers", {}).update(mcp_config["mcpServers"])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            print(f"  [OK] 已写入: {target}")
        except Exception as e:
            print(f"  [!!] 写入失败: {e}")
            print("  请手动复制上面的 JSON 到文件中。")

    settings_target = os.path.expanduser("~/.claude/settings.json")
    print(f"\n  还需在 {settings_target} 中添加:")
    print('  "enabledMcpjsonServers": ["geogebra"]')
    if ask("是否自动添加？"):
        try:
            settings = {}
            if os.path.exists(settings_target):
                with open(settings_target, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            servers = settings.setdefault("enabledMcpjsonServers", [])
            if "geogebra" not in servers:
                servers.append("geogebra")
            os.makedirs(os.path.dirname(settings_target), exist_ok=True)
            with open(settings_target, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            print(f"  [OK] 已更新: {settings_target}")
        except Exception as e:
            print(f"  [!!] 写入失败: {e}")


def step_summary():
    section("安装完成")
    print("  接下来的步骤：")
    print("  1. 双击 start_geogebra.* 启动 GeoGebra（或让 MCP Server 自动启动）")
    print("  2. 重启 Claude Code")
    print('  3. 在对话中说 "画一个曲柄摇杆机构" 开始使用')
    print(f"\n  项目目录: {PROJECT_DIR}")
    print(f"  仓库地址: https://github.com/123pc/Geogebra_mcp")


# ── 主流程 ──

def interactive_setup():
    print("╔═══════════════════════════════════════════════════╗")
    print("║     GeoGebra MCP Server — 一键安装向导           ║")
    print("╚═══════════════════════════════════════════════════╝")

    if not step_check_env():
        print("\n  请先安装缺失的依赖后重新运行。")
        sys.exit(1)

    if not ask("继续安装 Python 依赖？"):
        sys.exit(0)

    step_install_python_deps()
    step_install_node_deps()

    geogebra_path = step_find_geogebra()
    step_create_launcher(geogebra_path)
    step_generate_mcp_config()
    step_summary()


if __name__ == "__main__":
    interactive_setup()
