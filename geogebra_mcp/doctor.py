"""Environment diagnostics for GeoGebra MCP."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

from .auto_launcher import find_geogebra_installation, get_cdp_port, is_cdp_ready


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _run_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return str(exc)
    return (result.stdout or result.stderr).strip()


def run_checks() -> list[CheckResult]:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_js = os.path.join(package_dir, "geogebra_daemon.js")
    package_json = os.path.join(package_dir, "package.json")
    node = shutil.which("node")
    npm = shutil.which("npm")
    geogebra_path = find_geogebra_installation()
    port = get_cdp_port()

    checks = [
        CheckResult("python", sys.version_info >= (3, 10), sys.version.split()[0]),
        CheckResult("node", node is not None, node or "node not found on PATH"),
        CheckResult("npm", npm is not None, npm or "npm not found on PATH"),
        CheckResult("daemon_js", os.path.exists(daemon_js), daemon_js),
        CheckResult("package_json", os.path.exists(package_json), package_json),
        CheckResult("geogebra_install", geogebra_path is not None, geogebra_path or "GeoGebra Classic 6 not found"),
        CheckResult("cdp_port", is_cdp_ready(port=port), f"localhost:{port}"),
    ]

    if node:
        checks.append(CheckResult("node_version", True, _run_version(["node", "--version"])))
    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines = ["GeoGebra MCP doctor"]
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    if not all(check.ok for check in checks):
        lines.append("")
        lines.append("If cdp_port fails, start GeoGebra Classic 6 with --remote-debugging-port or let the MCP server auto-launch it.")
        lines.append("If daemon_js or package_json fails, reinstall the package from a fixed wheel or run from source.")
    return "\n".join(lines)


def main() -> None:
    checks = run_checks()
    print(format_checks(checks))
    raise SystemExit(0 if all(check.ok for check in checks) else 1)


if __name__ == "__main__":
    main()
