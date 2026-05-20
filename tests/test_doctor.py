import os
from geogebra_mcp.doctor import CheckResult, format_checks, _get_backend


def test_format_checks_success():
    output = format_checks([CheckResult("python", True, "3.12")])
    assert "[OK] python: 3.12" in output


def test_format_checks_failure_includes_hint():
    # With default auto backend, hints are web-oriented
    output = format_checks([CheckResult("cdp_port", False, "localhost:9222")])
    assert "[FAIL] cdp_port: localhost:9222" in output
    assert "reinstall" in output
    assert "npm install" in output


def test_skip_status_shows_skip():
    output = format_checks([CheckResult("geogebra_install", True, "not required for backend=web", "SKIP")])
    assert "[SKIP] geogebra_install" in output


def test_warn_status_shows_warn():
    output = format_checks([CheckResult("geogebra_cdn", True, "checked during first Web Runtime launch", "WARN")])
    assert "[WARN] geogebra_cdn" in output


def test_get_backend_defaults_to_auto():
    old = os.environ.pop("GEOGEBRA_BACKEND", None)
    try:
        assert _get_backend() == "auto"
    finally:
        if old is not None:
            os.environ["GEOGEBRA_BACKEND"] = old


def test_get_backend_returns_web():
    os.environ["GEOGEBRA_BACKEND"] = "web"
    assert _get_backend() == "web"
    del os.environ["GEOGEBRA_BACKEND"]


def test_web_bundle_mode_default_is_cdn():
    old_bundle = os.environ.pop("GEOGEBRA_WEB_BUNDLE", None)
    old_port = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    try:
        from geogebra_mcp.doctor import run_checks
        checks = run_checks()
        mode_check = next(c for c in checks if c.name == "web_bundle_mode")
        assert mode_check.detail == "cdn"
    finally:
        if old_bundle is not None:
            os.environ["GEOGEBRA_WEB_BUNDLE"] = old_bundle
        if old_port is not None:
            os.environ["GEOGEBRA_CDP_PORT"] = old_port


def test_web_bundle_local_missing_path_shows_fail():
    os.environ["GEOGEBRA_BACKEND"] = "web"
    os.environ["GEOGEBRA_WEB_BUNDLE"] = "local"
    old_port = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    old_path = os.environ.pop("GEOGEBRA_WEB_BUNDLE_PATH", None)
    os.environ["GEOGEBRA_WEB_BUNDLE_PATH"] = "/nonexistent/geogebra_bundle_test"
    try:
        from geogebra_mcp.doctor import run_checks
        checks = run_checks()
        path_check = next(c for c in checks if c.name == "web_bundle_path")
        assert path_check.status == "FAIL"
    finally:
        del os.environ["GEOGEBRA_BACKEND"]
        del os.environ["GEOGEBRA_WEB_BUNDLE"]
        del os.environ["GEOGEBRA_WEB_BUNDLE_PATH"]
        if old_path is not None:
            os.environ["GEOGEBRA_WEB_BUNDLE_PATH"] = old_path
        if old_port is not None:
            os.environ["GEOGEBRA_CDP_PORT"] = old_port


def test_web_bundle_cdn_does_not_require_path():
    os.environ["GEOGEBRA_BACKEND"] = "web"
    os.environ["GEOGEBRA_WEB_BUNDLE"] = "cdn"
    old_port = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    try:
        from geogebra_mcp.doctor import run_checks
        checks = run_checks()
        names = {c.name for c in checks}
        assert "web_bundle_path" not in names
    finally:
        del os.environ["GEOGEBRA_BACKEND"]
        del os.environ["GEOGEBRA_WEB_BUNDLE"]
        if old_port is not None:
            os.environ["GEOGEBRA_CDP_PORT"] = old_port


def test_web_backend_skips_cdp():
    os.environ["GEOGEBRA_BACKEND"] = "web"
    old_port = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    try:
        checks = __import__("geogebra_mcp.doctor", fromlist=["run_checks"]).run_checks()
        cdp = next(c for c in checks if c.name == "cdp_port")
        assert cdp.status == "SKIP"
    finally:
        os.environ.pop("GEOGEBRA_BACKEND", None)
        if old_port is not None:
            os.environ["GEOGEBRA_CDP_PORT"] = old_port
