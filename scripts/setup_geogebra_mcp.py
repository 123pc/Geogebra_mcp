"""Set up GeoGebra MCP for local agent clients.

This script is intentionally standard-library only. It is meant to be run by an
AI coding agent after the user clones the repository and asks for setup.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SKILLS = ("use-geogebra-mcp", "geogebra-master", "geogebra-setup")
BEGIN_MARKER = "# >>> geogebra-mcp managed block >>>"
END_MARKER = "# <<< geogebra-mcp managed block <<<"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"+ {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_DIR, text=True)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        raise SystemExit(
            f"Invalid JSON in {path}. A backup was written to {backup}. "
            "Please fix the file and rerun setup."
        ) from exc


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {path}")


def toml_quote(value: str) -> str:
    return json.dumps(value)


def remove_managed_block(text: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        return text.rstrip()
    end += len(END_MARKER)
    return (text[:start] + text[end:]).rstrip()


def remove_codex_geogebra_section(text: str) -> str:
    """Remove an existing unmanaged Codex geogebra MCP section if present."""
    text = remove_managed_block(text)
    pattern = r"(?ms)^\[mcp_servers\.geogebra\]\s*.*?(?=^\[|\Z)"
    return re.sub(pattern, "", text).rstrip()


def mcp_command() -> tuple[str, list[str]]:
    # Use the current Python executable instead of relying on PATH scripts. This
    # is more reliable for globally launched agents after editable installation.
    return sys.executable, ["-m", "geogebra_mcp.server"]


def install_dependencies(skip_deps: bool) -> None:
    if skip_deps:
        print("[SKIP] dependency installation")
        return
    run(["npm", "install"])
    run([sys.executable, "-m", "pip", "install", "-e", "."])


def configure_claude() -> None:
    command, args = mcp_command()
    home = Path.home()
    mcp_path = home / ".claude" / ".mcp.json"
    settings_path = home / ".claude" / "settings.json"

    mcp = load_json(mcp_path)
    mcp.setdefault("mcpServers", {})["geogebra"] = {
        "command": command,
        "args": args,
    }
    write_json(mcp_path, mcp)

    settings = load_json(settings_path)
    servers = settings.setdefault("enabledMcpjsonServers", [])
    if "geogebra" not in servers:
        servers.append("geogebra")
    write_json(settings_path, settings)


def configure_codex() -> None:
    command, args = mcp_command()
    path = Path.home() / ".codex" / "config.toml"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = remove_codex_geogebra_section(existing)
    args_toml = "[" + ", ".join(toml_quote(arg) for arg in args) + "]"
    block = "\n".join(
        [
            BEGIN_MARKER,
            "[mcp_servers.geogebra]",
            f"command = {toml_quote(command)}",
            f"args = {args_toml}",
            END_MARKER,
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((existing + "\n\n" + block + "\n").lstrip(), encoding="utf-8")
    print(f"[OK] wrote {path}")


def copy_skill(src: Path, dst_root: Path) -> None:
    if not src.exists():
        print(f"[WARN] missing skill: {src}")
        return
    dst = dst_root / src.name
    dst_root.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"[OK] installed skill {src.name} -> {dst}")


def install_skills() -> None:
    roots = [
        Path.home() / ".codex" / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
    ]
    for root in roots:
        for name in SKILLS:
            copy_skill(PROJECT_DIR / "skills" / name, root)


def run_bundle_setup() -> None:
    bundle_script = PROJECT_DIR / "scripts" / "setup_geogebra_web_bundle.py"
    if not bundle_script.exists():
        print("[WARN] bundle setup script not found, skipping")
        return
    print("\nDownloading offline GeoGebra Web Bundle:")
    result = run([sys.executable, str(bundle_script)], check=False)
    if result.returncode != 0:
        print("[WARN] Bundle download failed. CDN mode remains the default.")
        print("  Rerun: python scripts/setup_geogebra_web_bundle.py")


def run_doctor() -> None:
    print("\nRunning environment diagnostics:")
    result = run([sys.executable, "-m", "geogebra_mcp.doctor"], check=False)
    if result.returncode != 0:
        print(
            "\n[NOTE] geogebra-mcp-doctor returned a non-zero status. "
            "If only cdp_port failed, that is expected when GeoGebra is closed; "
            "the first MCP tool call should attempt auto-launch."
        )


def configure_agents(agent: str) -> None:
    if agent in ("all", "claude"):
        configure_claude()
    if agent in ("all", "codex"):
        configure_codex()


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up GeoGebra MCP for AI agents.")
    parser.add_argument(
        "--agent",
        choices=("all", "claude", "codex", "none"),
        default="all",
        help="Which global MCP client config to update. Default: all.",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip npm install and pip editable install.",
    )
    parser.add_argument(
        "--skip-skills",
        action="store_true",
        help="Do not copy bundled skills into user skill directories.",
    )
    parser.add_argument(
        "--skip-doctor",
        action="store_true",
        help="Do not run geogebra-mcp-doctor after setup.",
    )
    parser.add_argument(
        "--with-web-bundle",
        action="store_true",
        help="Download GeoGebra Math Apps Bundle for offline Web Runtime.",
    )
    parser.add_argument(
        "--skip-web-bundle",
        action="store_true",
        help="Skip web bundle download (default behavior).",
    )
    args = parser.parse_args()

    print("GeoGebra MCP setup")
    print(f"Project: {PROJECT_DIR}")

    install_dependencies(skip_deps=args.skip_deps)
    if args.agent != "none":
        configure_agents(args.agent)
    if not args.skip_skills:
        install_skills()
    if args.with_web_bundle and not args.skip_web_bundle:
        run_bundle_setup()
    if not args.skip_doctor:
        run_doctor()

    print(
        "\nDone. Restart your agent session, then ask: "
        "'Use GeoGebra MCP to check status and draw a triangle.'"
    )
    print(
        "\nGeoGebra Classic 6 is no longer required for the default Web Runtime.\n"
        "The first use may download Chromium through Puppeteer.\n"
        "Set GEOGEBRA_BACKEND=desktop to use an existing Classic 6 desktop install.\n"
        "Run with --with-web-bundle to download offline GeoGebra Math Apps Bundle."
    )


if __name__ == "__main__":
    main()
