"""Update GeoGebra MCP to the latest version from GitHub.

Usage: python update.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    label = " ".join(cmd)
    print(f"\n> {label}")
    result = subprocess.run(cmd, cwd=PROJECT_DIR, text=True)
    if check and result.returncode != 0:
        print(f"[FAIL] {label}")
        raise SystemExit(result.returncode)
    print(f"[OK]  {label}")
    return result


def main() -> None:
    print("Updating GeoGebra MCP …")
    print(f"Project: {PROJECT_DIR}")

    run(["git", "pull", "origin", "main"])
    run(["npm", "install"])
    run([sys.executable, "-m", "pip", "install", "-e", "."])

    # Re-run setup to sync MCP config and skills
    setup_script = PROJECT_DIR / "scripts" / "setup_geogebra_mcp.py"
    if setup_script.exists():
        run([sys.executable, str(setup_script), "--skip-deps", "--agent", "all"])
    else:
        print("[WARN] setup script not found, skipping config sync")

    print("\nUpdated. Restart your AI client session to pick up changes.")


if __name__ == "__main__":
    main()
