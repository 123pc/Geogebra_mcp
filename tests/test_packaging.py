"""Verify package resources are accessible after install."""

import os
import geogebra_mcp.server as server


def test_daemon_js_resource_exists():
    assert os.path.exists(server.DAEMON_JS)
    assert server.DAEMON_JS.endswith("geogebra_daemon.js")


def test_package_imports_server():
    import geogebra_mcp.server as s
    assert s.__version__ == "0.1.0"


def test_package_dir_exists():
    expected = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "geogebra_mcp")
    assert os.path.isdir(expected)
