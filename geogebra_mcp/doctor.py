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
    status: str = "OK"  # OK, FAIL, WARN, SKIP


def _run_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return str(exc)
    return (result.stdout or result.stderr).strip()


def _get_backend() -> str:
    raw = os.environ.get("GEOGEBRA_BACKEND", "auto")
    value = raw.lower()
    if value not in ("auto", "web", "desktop"):
        return "auto"
    return value


def _get_web_bundle_path():
    override = os.environ.get("GEOGEBRA_WEB_BUNDLE_PATH", "").strip()
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "geogebra_mcp", "web_bundle")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Caches", "geogebra_mcp", "web_bundle")
    cache_home = os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    return os.path.join(cache_home, "geogebra_mcp", "web_bundle")


def run_checks() -> list[CheckResult]:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_js = os.path.join(package_dir, "geogebra_daemon.js")
    package_json = os.path.join(package_dir, "package.json")
    web_index = os.path.join(package_dir, "web", "index.html")
    web_runtime = os.path.join(package_dir, "web", "runtime.js")
    node = shutil.which("node")
    npm = shutil.which("npm")
    backend = _get_backend()
    port = get_cdp_port()

    checks = [
        CheckResult("python", sys.version_info >= (3, 10), sys.version.split()[0]),
        CheckResult("node", node is not None, node or "node not found on PATH"),
        CheckResult("npm", npm is not None, npm or "npm not found on PATH"),
        CheckResult("daemon_js", os.path.exists(daemon_js), daemon_js),
        CheckResult("package_json", os.path.exists(package_json), package_json),
        CheckResult("backend", True, backend),
    ]

    # Web runtime checks — check root package.json (where npm install runs)
    puppeteer_ok = False
    root_pkg_json = os.path.join(os.path.dirname(package_dir), "package.json")
    for p in (package_json, root_pkg_json):
        if os.path.exists(p):
            try:
                import json
                pkg = json.load(open(p))
                if "puppeteer" in pkg.get("dependencies", {}):
                    puppeteer_ok = True
                    break
            except Exception:
                pass

    web_assets_ok = os.path.exists(web_index) and os.path.exists(web_runtime)
    if backend != "desktop":
        checks.append(CheckResult(
            "web_assets",
            web_assets_ok,
            package_dir if web_assets_ok else f"missing web/index.html or runtime.js",
            "OK" if web_assets_ok else "FAIL"
        ))
        checks.append(CheckResult(
            "puppeteer",
            puppeteer_ok,
            "installed" if puppeteer_ok else "puppeteer not in package.json dependencies",
            "OK" if puppeteer_ok else "WARN"
        ))
        checks.append(CheckResult("geogebra_cdn", True, "checked during first Web Runtime launch", "WARN"))

        # Web bundle checks (Phase 2 offline mode)
        web_bundle_mode = os.environ.get("GEOGEBRA_WEB_BUNDLE", "cdn").lower()
        checks.append(CheckResult("web_bundle_mode", True, web_bundle_mode, "OK" if web_bundle_mode == "cdn" else "INFO"))

        if web_bundle_mode == "local":
            bundle_dir = _get_web_bundle_path()
            bundle_ok = bundle_dir is not None and os.path.isdir(bundle_dir)
            checks.append(CheckResult(
                "web_bundle_path",
                bundle_ok,
                str(bundle_dir) if bundle_ok else "bundle path not found",
                "OK" if bundle_ok else "FAIL"
            ))
            if bundle_ok:
                deployggb = os.path.join(str(bundle_dir), "GeoGebra", "deployggb.js")
                has_deployggb = os.path.isfile(deployggb)
                codebase_dir = os.path.join(str(bundle_dir), "GeoGebra", "HTML5", "5.0", "web3d")
                has_codebase = os.path.isdir(codebase_dir)
                checks.append(CheckResult(
                    "web_bundle_deployggb",
                    has_deployggb and has_codebase,
                    deployggb if has_deployggb else "GeoGebra/deployggb.js or HTML5 codebase missing from bundle",
                    "OK" if (has_deployggb and has_codebase) else "FAIL"
                ))

    # Desktop-specific checks
    geogebra_path = find_geogebra_installation()
    if backend == "desktop":
        checks.append(CheckResult(
            "geogebra_install",
            geogebra_path is not None,
            geogebra_path or "GeoGebra Classic 6 not found",
        ))
        checks.append(CheckResult(
            "cdp_port",
            is_cdp_ready(port=port),
            f"localhost:{port}",
        ))
    else:
        checks.append(CheckResult("geogebra_install", True, "not required for backend=" + backend, "SKIP"))
        checks.append(CheckResult("cdp_port", True, "not required for backend=" + backend, "SKIP"))

    if node:
        checks.append(CheckResult("node_version", True, _run_version(["node", "--version"])))
    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines = ["GeoGebra MCP doctor"]
    for check in checks:
        mark = check.status if check.status != "OK" else ("OK" if check.ok else "FAIL")
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    if not all(check.ok for check in checks):
        lines.append("")
        backend = _get_backend()
        if backend == "desktop":
            lines.append("If cdp_port fails, start GeoGebra Classic 6 with --remote-debugging-port or let the MCP server auto-launch it.")
        else:
            lines.append("If web_assets or puppeteer fails, reinstall the package and run npm install.")
        bundle_mode = os.environ.get("GEOGEBRA_WEB_BUNDLE", "cdn").lower()
        if bundle_mode == "local":
            lines.append("If web_bundle checks fail, run: python scripts/setup_geogebra_web_bundle.py")
        lines.append("If daemon_js or package_json fails, reinstall the package from a fixed wheel or run from source.")
    return "\n".join(lines)


def main() -> None:
    checks = run_checks()
    print(format_checks(checks))
    raise SystemExit(0 if all(check.ok for check in checks) else 1)


if __name__ == "__main__":
    main()
