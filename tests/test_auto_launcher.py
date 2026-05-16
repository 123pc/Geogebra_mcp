"""Unit tests for auto_launcher.py — cross-platform GeoGebra detection & launch."""

import os
import sys
import urllib.error
from unittest.mock import patch, MagicMock, mock_open

import pytest

from auto_launcher import (
    get_cdp_port,
    get_search_paths,
    find_geogebra_installation,
    is_cdp_ready,
    geogebra_status_message,
    ensure_geogebra_running,
    CDP_PORT_DEFAULT,
)


# ── get_cdp_port ──


class TestGetCdpPort:
    def test_default(self, clean_env):
        assert get_cdp_port() == CDP_PORT_DEFAULT

    def test_env_override(self):
        os.environ["GEOGEBRA_CDP_PORT"] = "9233"
        assert get_cdp_port() == 9233

    def test_invalid_env(self):
        os.environ["GEOGEBRA_CDP_PORT"] = "not_a_number"
        with pytest.raises(ValueError):
            get_cdp_port()


# ── get_search_paths ──


class TestGetSearchPaths:
    @patch("sys.platform", "win32")
    @patch("glob.glob")
    def test_windows_paths(self, mock_glob):
        mock_glob.return_value = [r"C:\Users\test\AppData\Local\GeoGebra_6\app-6.0.8890\GeoGebra.exe"]
        with patch.dict(
            os.environ,
            {"LOCALAPPDATA": r"C:\Users\test\AppData\Local", "PROGRAMFILES": r"C:\Program Files"},
            clear=True,
        ):
            paths = get_search_paths()
            assert any("GeoGebra_6" in p for p in paths)
            assert any("app-" in p for p in paths)

    @patch("sys.platform", "darwin")
    def test_macos_paths(self):
        paths = get_search_paths()
        assert any("GeoGebra" in p for p in paths)
        assert any(".app" in p for p in paths)

    @patch("sys.platform", "linux")
    def test_linux_paths(self):
        paths = get_search_paths()
        assert "/usr/bin/geogebra-classic" in paths
        assert "/usr/bin/geogebra" in paths

    @patch("sys.platform", "linux")
    def test_no_duplicates(self):
        paths = get_search_paths()
        assert len(paths) == len(set(paths))


# ── find_geogebra_installation ──


class TestFindGeogebraInstallation:
    @patch("sys.platform", "win32")
    @patch("os.path.isfile")
    def test_finds_windows_exe(self, mock_isfile, clean_env):
        mock_isfile.side_effect = lambda p: p.endswith("GeoGebra.exe")
        with patch.dict(
            os.environ,
            {"LOCALAPPDATA": r"C:\Users\test\AppData\Local", "PROGRAMFILES": r"C:\Program Files"},
            clear=True,
        ):
            result = find_geogebra_installation()
            assert result is not None
            assert "GeoGebra.exe" in result

    @patch("sys.platform", "linux")
    @patch("os.path.isfile")
    def test_finds_linux_binary(self, mock_isfile, clean_env):
        mock_isfile.side_effect = lambda p: p == "/usr/bin/geogebra-classic"
        result = find_geogebra_installation()
        assert result == "/usr/bin/geogebra-classic"

    @patch("sys.platform", "linux")
    @patch("os.path.isfile")
    def test_none_when_missing(self, mock_isfile, clean_env):
        mock_isfile.return_value = False
        result = find_geogebra_installation()
        assert result is None


# ── is_cdp_ready ──


class TestIsCdpReady:
    @patch("urllib.request.urlopen")
    def test_ready(self, mock_urlopen, clean_env):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value = mock_resp
        assert is_cdp_ready(port=9222) is True

    @patch("urllib.request.urlopen")
    def test_not_ready_connection_refused(self, mock_urlopen, clean_env):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        assert is_cdp_ready(port=9222) is False

    @patch("urllib.request.urlopen")
    def test_not_ready_timeout(self, mock_urlopen, clean_env):
        mock_urlopen.side_effect = TimeoutError()
        assert is_cdp_ready(port=9222) is False

    @patch("urllib.request.urlopen")
    def test_not_ready_wrong_status(self, mock_urlopen, clean_env):
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_urlopen.return_value = mock_resp
        assert is_cdp_ready(port=9222) is False


# ── geogebra_status_message ──


class TestGeogebraStatusMessage:
    def test_contains_port_info(self, clean_env):
        msg = geogebra_status_message(port=9222)
        assert "9222" in msg
        assert "geogebra.org/download" in msg

    @patch("sys.platform", "win32")
    def test_windows_hint(self, clean_env):
        msg = geogebra_status_message()
        assert "GeoGebra.exe" in msg

    @patch("sys.platform", "darwin")
    def test_macos_hint(self, clean_env):
        msg = geogebra_status_message()
        assert "open -a" in msg

    @patch("sys.platform", "linux")
    def test_linux_hint(self, clean_env):
        msg = geogebra_status_message()
        assert "geogebra-classic" in msg

    def test_bilingual_output(self, clean_env):
        msg = geogebra_status_message()
        assert "CDP port" in msg
        assert "CDP 端口" in msg


# ── ensure_geogebra_running ──


class TestEnsureGeogebraRunning:
    @patch("auto_launcher.is_cdp_ready")
    def test_already_running(self, mock_ready, clean_env):
        mock_ready.return_value = True
        assert ensure_geogebra_running(port=9222) is True

    @patch("auto_launcher.find_geogebra_installation")
    @patch("auto_launcher.is_cdp_ready")
    def test_not_found(self, mock_ready, mock_find, clean_env):
        mock_ready.return_value = False
        mock_find.return_value = None
        assert ensure_geogebra_running(port=9222) is False

    @patch("auto_launcher.launch_geogebra")
    @patch("auto_launcher.find_geogebra_installation")
    @patch("auto_launcher.is_cdp_ready")
    def test_launches_when_found(self, mock_ready, mock_find, mock_launch, clean_env):
        mock_ready.return_value = False
        mock_find.return_value = "/fake/GeoGebra.exe"

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process still running
        mock_launch.return_value = mock_proc

        assert ensure_geogebra_running(port=9222) is True
        mock_launch.assert_called_once()

    @patch("auto_launcher.launch_geogebra")
    @patch("auto_launcher.find_geogebra_installation")
    @patch("auto_launcher.is_cdp_ready")
    def test_launch_fails_process_dies(self, mock_ready, mock_find, mock_launch, clean_env):
        mock_ready.return_value = False
        mock_find.return_value = "/fake/GeoGebra.exe"
        mock_launch.return_value = None  # Process died

        assert ensure_geogebra_running(port=9222) is False
