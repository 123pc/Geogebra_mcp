from geogebra_mcp.doctor import CheckResult, format_checks


def test_format_checks_success():
    output = format_checks([CheckResult("python", True, "3.12")])
    assert "[OK] python: 3.12" in output


def test_format_checks_failure_includes_hint():
    output = format_checks([CheckResult("cdp_port", False, "localhost:9222")])
    assert "[FAIL] cdp_port: localhost:9222" in output
    assert "--remote-debugging-port" in output
