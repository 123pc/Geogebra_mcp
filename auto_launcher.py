"""
GeoGebra 自动查找与启动模块
跨平台扫描 GeoGebra Classic 6 安装位置，自动启动并等待 CDP 就绪。
当检测到 GeoGebra 已安装但未以调试模式运行时，自动终止旧进程并重新启动。
"""

import os
import sys
import subprocess
import time
import glob
import urllib.request
import urllib.error
from typing import Optional, List

CDP_PORT_DEFAULT = 9222


def get_cdp_port() -> int:
    return int(os.environ.get("GEOGEBRA_CDP_PORT", str(CDP_PORT_DEFAULT)))


# ── 平台搜索路径 ──

def get_search_paths() -> List[str]:
    system = sys.platform
    paths = []

    if system == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            base = os.path.join(local_appdata, "GeoGebra_6")
            versioned = sorted(
                glob.glob(os.path.join(base, "app-*", "GeoGebra.exe")),
                reverse=True,
            )
            paths.extend(versioned)
            paths.append(os.path.join(base, "GeoGebra.exe"))

        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            pf = os.environ.get(var, "")
            if pf:
                paths.append(os.path.join(pf, "GeoGebra 6", "GeoGebra.exe"))
                paths.append(os.path.join(pf, "GeoGebra", "GeoGebra.exe"))

    elif system == "darwin":
        candidates = [
            "/Applications/GeoGebra Classic 6.app/Contents/MacOS/GeoGebra*",
            "/Applications/GeoGebra.app/Contents/MacOS/GeoGebra*",
            os.path.expanduser("~/Applications/GeoGebra Classic 6.app/Contents/MacOS/GeoGebra*"),
        ]
        for pattern in candidates:
            paths.extend(sorted(glob.glob(pattern)))
        paths.append("/Applications/GeoGebra Classic 6.app")

    else:
        paths.extend([
            "/usr/bin/geogebra-classic",
            "/usr/bin/geogebra",
            "/usr/local/bin/geogebra-classic",
            "/opt/GeoGebra/GeoGebra",
            "/opt/geogebra/GeoGebra",
        ])
        home = os.path.expanduser("~")
        paths.extend(sorted(
            glob.glob(os.path.join(home, ".local", "share", "GeoGebra*", "GeoGebra"))
        ))

    return list(dict.fromkeys(p for p in paths if p))


def find_geogebra_installation() -> Optional[str]:
    for candidate in get_search_paths():
        if candidate.endswith(".app"):
            if os.path.isdir(candidate):
                return candidate
        elif os.path.isfile(candidate):
            return candidate
        if sys.platform == "darwin" and os.path.isdir(candidate):
            macos_dir = os.path.join(candidate, "Contents", "MacOS")
            if os.path.isdir(macos_dir):
                for name in os.listdir(macos_dir):
                    full = os.path.join(macos_dir, name)
                    if os.access(full, os.X_OK):
                        return full
    return None


# ── CDP 端口检测 ──

def is_cdp_ready(host: str = "localhost", port: int = None, timeout: float = 1.5) -> bool:
    port = port or get_cdp_port()
    try:
        resp = urllib.request.urlopen(
            f"http://{host}:{port}/json/version", timeout=timeout
        )
        return resp.status == 200
    except Exception:
        return False


# ── 进程管理 ──

def _kill_existing_geogebra() -> int:
    """终止已有的 GeoGebra 进程（不带 CDP 端口运行的）。返回杀掉的进程数。"""
    killed = 0
    system = sys.platform
    try:
        if system == "win32":
            result = subprocess.run(
                ["taskkill", "/f", "/im", "GeoGebra.exe"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                killed = 1
        elif system == "darwin":
            result = subprocess.run(
                ["pkill", "-f", "GeoGebra"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                killed = 1
        else:
            result = subprocess.run(
                ["pkill", "-f", "geogebra"],
                capture_output=True, text=True, timeout=10,
            )
            killed = 1 if result.returncode == 0 else 0
    except Exception:
        pass
    return killed


# ── 启动 GeoGebra ──

def launch_geogebra(
    geogebra_path: str,
    port: int = None,
    wait: bool = True,
    startup_timeout: float = 45.0,
) -> Optional[subprocess.Popen]:
    port = port or get_cdp_port()
    system = sys.platform

    # Windows: use CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS so it doesn't
    # inherit our console and truly starts independently.
    kwargs = {}
    if system == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )

    if system == "darwin" and geogebra_path.endswith(".app"):
        proc = subprocess.Popen(
            ["open", geogebra_path, "--args", f"--remote-debugging-port={port}"],
            start_new_session=True, **kwargs,
        )
    else:
        proc = subprocess.Popen(
            [geogebra_path, f"--remote-debugging-port={port}"],
            start_new_session=True, **kwargs,
        )

    if not wait:
        return proc

    # 轮询等待 CDP 就绪
    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            # Process exited — but on Windows DETACHED_PROCESS makes poll()
            # return immediately (0) even though the child is running.
            # Only treat as failure on non-Windows.
            if system != "win32":
                return None
        if is_cdp_ready(port=port):
            return proc
        time.sleep(1.0)

    # 超时: 进程可能还在但 CDP 没就绪
    if proc.poll() is None:
        return proc  # Still running, maybe CDP will come up later
    return None


# ── 重启策略 ──

def should_restart_existing_geogebra() -> bool:
    """检查环境变量，决定是否自动终止已有的 GeoGebra 进程。默认不终止，保护用户未保存工作。"""
    return os.environ.get("GEOGEBRA_RESTART_EXISTING", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


# ── 主入口 ──

def ensure_geogebra_running(port: int = None) -> bool:
    """
    确保 GeoGebra 以调试模式运行。策略:
    1. CDP 已就绪 → 直接返回 True
    2. 未就绪且 opt-in → 杀掉旧 GeoGebra（普通启动的没有 CDP）
    3. 找到安装 → 以 --remote-debugging-port 重新启动
    """
    port = port or get_cdp_port()

    # 1. 已经可用了
    if is_cdp_ready(port=port):
        return True

    # 2. 仅在 opt-in 时杀掉旧实例（保护用户未保存工作）
    if should_restart_existing_geogebra():
        _kill_existing_geogebra()
        time.sleep(1.5)

    # 3. 找到安装
    geogebra_path = find_geogebra_installation()
    if not geogebra_path:
        return False

    # 4. 启动并等待
    proc = launch_geogebra(geogebra_path, port=port, wait=True, startup_timeout=45.0)
    if proc is None:
        return False

    # 进程可能仍在运行但没有 CDP → 仅在 opt-in 时再杀一次，重试
    if not is_cdp_ready(port=port):
        if should_restart_existing_geogebra():
            _kill_existing_geogebra()
            time.sleep(1.0)
            proc = launch_geogebra(geogebra_path, port=port, wait=True, startup_timeout=30.0)
            if proc is None:
                return False

    return is_cdp_ready(port=port) or (proc is not None and proc.poll() is None)


def geogebra_status_message(port: int = None) -> str:
    port = port or get_cdp_port()
    lines = [
        f"GeoGebra Classic 6 CDP port: {port} / CDP 端口: {port}",
        "Please ensure GeoGebra is installed and running: / 请确保已安装并启动 GeoGebra:",
    ]
    if sys.platform == "win32":
        lines.append(
            '  Windows: "%LOCALAPPDATA%\\GeoGebra_6\\app-<version>\\GeoGebra.exe"'
            f" --remote-debugging-port={port}"
        )
    elif sys.platform == "darwin":
        lines.append(
            f"  macOS: open -a 'GeoGebra Classic 6' --args --remote-debugging-port={port}"
        )
    else:
        lines.append(f"  Linux: geogebra-classic --remote-debugging-port={port}")
    lines.append("  Download / 下载: https://www.geogebra.org/download")
    return "\n".join(lines)
