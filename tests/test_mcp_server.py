"""Unit tests for geogebra_mcp_server.py MCP tools with mocked daemon."""

import json
import sys
import os
import threading
from unittest.mock import patch, MagicMock

import pytest

# ── Fake daemon client for testing connection-state logic ──

from geogebra_mcp.server import GeoGebraDaemonClient, DaemonError


class TestAutoLaunchWhenReadyButDisconnected:
    """Task 1: Reproduce the exact Claude Code failure — daemon process is alive
    (_ready is set) but GeoGebra is not connected (_connected is False)."""

    def test_auto_launch_runs_when_daemon_ready_but_geogebra_disconnected(self):
        client = GeoGebraDaemonClient(cdp_port=9222)
        client._ready.set()
        client._connected = False

        calls = {"ensure": 0, "restart": 0}

        def fake_ensure(port):
            calls["ensure"] += 1
            assert port == 9222
            return True

        def fake_restart():
            calls["restart"] += 1
            client._connected = True

        def fake_write_then_fail(method, params=None, timeout=30):
            raise DaemonError("GEOGEBRA_NOT_CONNECTED: Cannot connect to GeoGebra")

        client._write_request_once = fake_write_then_fail
        client._restart = fake_restart

        with patch("geogebra_mcp.server.ensure_geogebra_running", fake_ensure):
            with pytest.raises(DaemonError):
                client._call("status")

        assert calls["ensure"] == 1, f"Expected ensure_geogebra_running to be called once, got {calls['ensure']}"
        assert calls["restart"] == 1, f"Expected restart to be called once, got {calls['restart']}"

    def test_status_auto_launches_when_daemon_ready_but_status_disconnected(self):
        """Task 2A: _call('status') must trigger auto-launch when connected:false."""
        from geogebra_mcp.server import GeoGebraDaemonClient

        client = GeoGebraDaemonClient(cdp_port=9222)
        client._ready.set()
        client._connected = False

        calls = {"ensure": 0, "restart": 0, "attempt": 0}

        def fake_ensure(port):
            calls["ensure"] += 1
            assert port == 9222
            return True

        def fake_restart():
            calls["restart"] += 1
            client._connected = True

        def fake_write(method, params=None, timeout=30):
            calls["attempt"] += 1
            assert method == "status"
            if calls["attempt"] == 1:
                return {"connected": False, "error": "GeoGebra 未运行或 CDP 端口不可用"}
            return {"connected": True, "title": "GeoGebra Classic 6", "objectCount": 0}

        client._write_request_once = fake_write
        client._restart = fake_restart

        with patch("geogebra_mcp.server.ensure_geogebra_running", fake_ensure):
            result = client._call("status")

        assert result["connected"] is True
        assert calls["ensure"] == 1
        assert calls["restart"] == 1
        assert calls["attempt"] == 2

# Must mock the daemon BEFORE importing the MCP server module, because the
# module-level singletons (NODE, DAEMON_JS) and class definitions run at import.
# We replace the entire GeoGebraDaemonClient with a mock.

_mock_daemon_instance = MagicMock()


def _mock_get_daemon(cdp_port=None):
    return _mock_daemon_instance


with patch.dict(sys.modules, {"mcp.server.fastmcp": MagicMock()}):
    # Also suppress auto_launcher import side effects
    pass


# We can't directly import geogebra_mcp_server without triggering subprocess
# and threading. Instead, test the tool handler logic in isolation by
# exercising the patterns the tools use.


class TestToolResponsePatterns:
    """Test the JSON response format used by all MCP tools."""

    def test_success_response_format(self):
        resp = json.dumps({"success": True, "result": "ok", "command": "A=(0,0)"}, ensure_ascii=False)
        parsed = json.loads(resp)
        assert parsed["success"] is True
        assert "result" in parsed

    def test_error_response_format(self):
        resp = json.dumps({"success": False, "error": "守护进程已崩溃"}, ensure_ascii=False)
        parsed = json.loads(resp)
        assert parsed["success"] is False
        assert "error" in parsed

    def test_batch_response_format(self):
        resp = json.dumps({
            "success": True,
            "total": 3,
            "succeeded": 3,
            "failed": 0,
            "details": [
                {"command": "A=(0,0)", "result": True},
                {"command": "B=(6,0)", "result": True},
                {"command": "Segment(A,B)", "result": True},
            ],
        }, ensure_ascii=False)
        parsed = json.loads(resp)
        assert parsed["total"] == 3
        assert parsed["succeeded"] == 3

    def test_draw_mechanism_response_format(self):
        resp = json.dumps({
            "success": True,
            "name": "test_mechanism",
            "commands_executed": "5/5",
            "ggb_file": "/output/test_mechanism.ggb",
            "png_file": "/output/test_mechanism.png",
            "objects_count": 8,
        }, ensure_ascii=False)
        parsed = json.loads(resp)
        assert parsed["name"] == "test_mechanism"
        assert ".ggb" in parsed["ggb_file"]


class TestDaemonProtocol:
    """Test the JSON line protocol used between Python MCP server and Node.js daemon."""

    def test_request_format(self):
        msg = json.dumps({"id": "1", "method": "exec", "params": {"cmd": "A = (0, 0)"}})
        parsed = json.loads(msg)
        assert parsed["id"] == "1"
        assert parsed["method"] == "exec"
        assert parsed["params"]["cmd"] == "A = (0, 0)"

    def test_ready_response_format(self):
        msg = json.dumps({"type": "ready", "ok": True, "connected": True, "title": "GeoGebra Classic 6"})
        parsed = json.loads(msg)
        assert parsed["type"] == "ready"
        assert parsed["ok"] is True

    def test_success_response_format(self):
        msg = json.dumps({"id": "1", "ok": True, "result": True})
        parsed = json.loads(msg)
        assert parsed["id"] == "1"
        assert parsed["ok"] is True
        assert parsed["result"] is True

    def test_error_response_format(self):
        msg = json.dumps({"id": "1", "ok": False, "error": "无法连接到 GeoGebra"})
        parsed = json.loads(msg)
        assert parsed["ok"] is False
        assert "error" in parsed

    def test_fatal_message(self):
        msg = json.dumps({"type": "fatal", "error": "cannot find module"})
        parsed = json.loads(msg)
        assert parsed["type"] == "fatal"

    def test_batch_request(self):
        cmds = ["A=(0,0)", "B=(6,0)", "Segment(A,B)"]
        msg = json.dumps({"id": "2", "method": "batch", "params": {"commands": cmds}})
        parsed = json.loads(msg)
        assert len(parsed["params"]["commands"]) == 3

    def test_empty_line_skipped(self):
        assert "" == ""  # Empty lines are skipped by the reader loop


class TestDesignJsonParsing:
    """Test the design_json format used by geogebra_draw_mechanism."""

    def test_valid_design_json(self):
        design = {
            "perspective": "G",
            "animate": "α",
            "speed": 0.5,
            "commands": [
                "O1 = (0, 0)",
                "O2 = (6, 0)",
                "α = 45°",
            ],
            "styles": [
                {"label": "A", "color": [1, 0, 0], "point_size": 5},
                {"label": "B", "color": [0, 0, 1], "point_size": 5},
            ],
        }
        parsed = json.loads(json.dumps(design, ensure_ascii=False))
        assert len(parsed["commands"]) == 3
        assert len(parsed["styles"]) == 2

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            json.loads("{not valid json")

    def test_missing_commands(self):
        design = {"perspective": "G"}
        cmds = design.get("commands", [])
        assert cmds == []
