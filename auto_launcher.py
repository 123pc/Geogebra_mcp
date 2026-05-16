"""
GeoGebra 自动查找与启动模块
跨平台扫描 GeoGebra Classic 6 安装位置，自动启动并等待 CDP 就绪。
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


def get_search_paths() -> List[str]:
    """返回当前平台上 GeoGebra Classic 6 可能的可执行路径列表（按优先级排序）"""
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
        # Also try open -a
        paths.append("/Applications/GeoGebra Classic 6.app")

    else:  # Linux / other Unix
        paths.extend(
            [
                "/usr/bin/geogebra-classic",
                "/usr/bin/geogebra",
                "/usr/local/bin/geogebra-classic",
                "/opt/GeoGebra/GeoGebra",
                "/opt/geogebra/GeoGebra",
            ]
        )
        home = os.path.expanduser("~")
        paths.extend(
            sorted(
                glob.glob(
                    os.path.join(home, ".local", "share", "GeoGebra*", "GeoGebra")
                )
            )
        )

    # 去重保留顺序
    return list(dict.fromkeys(p for p in paths if p))


def find_geogebra_installation() -> Optional[str]:
    for candidate in get_search_paths():
        if candidate.endswith(".app"):
            if os.path.isdir(candidate):
                return candidate
        elif os.path.isfile(candidate):
            return candidate
        # macOS: also check inside .app bundle if path points to directory
        if sys.platform == "darwin" and os.path.isdir(candidate):
            macos_dir = os.path.join(candidate, "Contents", "MacOS")
            if os.path.isdir(macos_dir):
                for name in os.listdir(macos_dir):
                    full = os.path.join(macos_dir, name)
                    if os.access(full, os.X_OK):
                        return full
    return None


def is_cdp_ready(host: str = "localhost", port: int = None, timeout: float = 1.5) -> bool:
    port = port or get_cdp_port()
    try:
        resp = urllib.request.urlopen(
            f"http://{host}:{port}/json/version", timeout=timeout
        )
        return resp.status == 200
    except Exception:
        return False


def launch_geogebra(
    geogebra_path: str,
    port: int = None,
    wait: bool = True,
    startup_timeout: float = 30.0,
) -> Optional[subprocess.Popen]:
    port = port or get_cdp_port()

    system = sys.platform
    if system == "darwin" and geogebra_path.endswith(".app"):
        proc = subprocess.Popen(
            ["open", geogebra_path, "--args", f"--remote-debugging-port={port}"],
            start_new_session=True,
        )
    elif system == "darwin":
        proc = subprocess.Popen(
            [geogebra_path, f"--remote-debugging-port={port}"],
            start_new_session=True,
        )
    else:
        proc = subprocess.Popen(
            [geogebra_path, f"--remote-debugging-port={port}"],
            start_new_session=True,
        )

    if wait:
        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                return None  # Process died immediately
            if is_cdp_ready(port=port):
                return proc
            time.sleep(0.8)
        return None  # Timeout

    return proc


def ensure_geogebra_running(port: int = None) -> bool:
    port = port or get_cdp_port()

    if is_cdp_ready(port=port):
        return True

    geogebra_path = find_geogebra_installation()
    if not geogebra_path:
        return False

    proc = launch_geogebra(geogebra_path, port=port, wait=True)
    return proc is not None and proc.poll() is None


def geogebra_status_message(port: int = None) -> str:
    port = port or get_cdp_port()
    lines = [
        f"GeoGebra Classic 6 CDP 端口: {port}",
        "请确保已安装并启动 GeoGebra:",
    ]
    if sys.platform == "win32":
        lines.append(
            '  Windows: "%LOCALAPPDATA%\\GeoGebra_6\\app-<版本>\\GeoGebra.exe"'
            f" --remote-debugging-port={port}"
        )
    elif sys.platform == "darwin":
        lines.append(
            f"  macOS: open -a 'GeoGebra Classic 6' --args --remote-debugging-port={port}"
        )
    else:
        lines.append(f"  Linux: geogebra-classic --remote-debugging-port={port}")
    lines.append("  下载: https://www.geogebra.org/download")
    return "\n".join(lines)
