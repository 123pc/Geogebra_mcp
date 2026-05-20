#!/usr/bin/env python3
"""Download and cache the GeoGebra Math Apps Bundle for offline Web Runtime.

Usage:
    python scripts/setup_geogebra_web_bundle.py          # download + verify
    python scripts/setup_geogebra_web_bundle.py --check  # verify existing only

Cache location:
    Windows:  %LOCALAPPDATA%/geogebra_mcp/web_bundle
    macOS:    ~/Library/Caches/geogebra_mcp/web_bundle
    Linux:    ~/.cache/geogebra_mcp/web_bundle
    Override: GEOGEBRA_WEB_BUNDLE_PATH
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request


def default_bundle_dir() -> Path:
    override = os.environ.get("GEOGEBRA_WEB_BUNDLE_PATH", "").strip()
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(base) / "geogebra_mcp" / "web_bundle"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "geogebra_mcp" / "web_bundle"
    cache_home = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    return Path(cache_home) / "geogebra_mcp" / "web_bundle"


def manifest_path() -> Path:
    return Path(__file__).resolve().parent.parent / "geogebra_mcp" / "web" / "bundle_manifest.json"


def load_manifest(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verify_bundle(bundle_dir: Path, required_files: list[str]) -> tuple[bool, list[str]]:
    missing = []
    for file in required_files:
        if not (bundle_dir / file).is_file():
            missing.append(file)
    return (len(missing) == 0, missing)


def download_bundle(url: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "geogebra-bundle.zip"

    print(f"Downloading GeoGebra Math Apps Bundle from {url} ...")
    req = Request(url, headers={"User-Agent": "geogebra-mcp-setup/1.0"})
    with urlopen(req, timeout=300) as resp:
        with open(zip_path, "wb") as fh:
            shutil.copyfileobj(resp, fh)

    file_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Downloaded: {file_size_mb:.1f} MB")

    print(f"Extracting to {dest_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    zip_path.unlink()
    print("Extraction complete.")


def main() -> None:
    check_only = "--check" in sys.argv

    try:
        manifest = load_manifest(manifest_path())
    except Exception as exc:
        print(f"FAIL: Cannot load bundle_manifest.json: {exc}")
        raise SystemExit(1)

    bundle_dir = default_bundle_dir()
    required = manifest.get("requiredFiles", [])
    source_url = manifest.get("source", "")

    print(f"Bundle source:  {source_url}")
    print(f"Cache dir:      {bundle_dir}")

    if check_only:
        ok, missing = verify_bundle(bundle_dir, required)
        if ok:
            print("Bundle check:   OK — all required files present")
            raise SystemExit(0)
        else:
            print(f"FAIL: Missing required files: {missing}")
            print("Run without --check to download the bundle.")
            raise SystemExit(1)

    ok, missing = verify_bundle(bundle_dir, required)
    if ok:
        print("Bundle already cached and valid. Use --check to verify only.")
    else:
        if missing:
            print(f"Missing files: {missing}")
        try:
            download_bundle(source_url, bundle_dir)
        except Exception as exc:
            print(f"FAIL: Download failed: {exc}")
            print("Check network connectivity and that the GeoGebra CDN is reachable.")
            raise SystemExit(1)

    ok, missing = verify_bundle(bundle_dir, required)
    if not ok:
        print(f"FAIL: Bundle verification failed. Missing: {missing}")
        raise SystemExit(1)

    print("Bundle verified OK.")
    print(f"Set GEOGEBRA_WEB_BUNDLE=local to use the offline bundle.")
    if sys.platform == "win32":
        print(f'  $env:GEOGEBRA_WEB_BUNDLE="local"')
    else:
        print(f'  export GEOGEBRA_WEB_BUNDLE=local')


if __name__ == "__main__":
    main()
