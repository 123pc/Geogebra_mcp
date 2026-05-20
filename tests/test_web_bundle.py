import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from setup_geogebra_web_bundle import default_bundle_dir, load_manifest, verify_bundle


def test_default_bundle_dir_env_override():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["GEOGEBRA_WEB_BUNDLE_PATH"] = tmp
        try:
            assert default_bundle_dir() == Path(tmp)
        finally:
            del os.environ["GEOGEBRA_WEB_BUNDLE_PATH"]


def test_default_bundle_dir_returns_path():
    d = default_bundle_dir()
    assert isinstance(d, Path)
    assert "geogebra_mcp" in d.parts or "GEOGEBRA_WEB_BUNDLE_PATH" in os.environ


def test_load_manifest():
    manifest_path = (
        Path(__file__).resolve().parent.parent
        / "geogebra_mcp" / "web" / "bundle_manifest.json"
    )
    manifest = load_manifest(manifest_path)
    assert manifest["name"] == "geogebra-math-apps-bundle"
    assert "source" in manifest
    assert "requiredFiles" in manifest
    assert isinstance(manifest["requiredFiles"], list)


def test_verify_bundle_all_present():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ggb_dir = base / "GeoGebra"
        ggb_dir.mkdir(parents=True)
        (ggb_dir / "deployggb.js").write_text("// deployggb stub")
        geo_dir = ggb_dir / "HTML5" / "5.0" / "web3d"
        geo_dir.mkdir(parents=True)
        (geo_dir / "web3d.nocache.js").write_text("// geogebra stub")

        ok, missing = verify_bundle(
            base,
            ["GeoGebra/deployggb.js", "GeoGebra/HTML5/5.0/web3d/web3d.nocache.js"],
        )
        assert ok is True
        assert missing == []


def test_verify_bundle_missing_files():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        ok, missing = verify_bundle(
            base,
            ["GeoGebra/deployggb.js", "GeoGebra/HTML5/5.0/web3d/web3d.nocache.js"],
        )
        assert ok is False
        assert "GeoGebra/deployggb.js" in missing


def test_manifest_required_files_are_strings():
    manifest_path = (
        Path(__file__).resolve().parent.parent
        / "geogebra_mcp" / "web" / "bundle_manifest.json"
    )
    manifest = load_manifest(manifest_path)
    for f in manifest["requiredFiles"]:
        assert isinstance(f, str)
