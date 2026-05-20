# GeoGebra MCP Reliability and Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GeoGebra MCP reliably auto-launch GeoGebra when AI clients call tools, and make the project safer and more universal for Claude Code, Codex, and other MCP clients.

**Architecture:** Separate "daemon process is alive" from "GeoGebra is connected" in the Python client, then trigger auto-launch on connection failures instead of only on daemon startup failure. Package the project as a real Python package so JS resources are installed with the wheel, add a doctor command for environment diagnosis, and strengthen tests around the exact failure reported from Claude Code.

**Tech Stack:** Python 3.10+, MCP FastMCP, Node.js, puppeteer-core, GeoGebra Classic 6 over Chrome DevTools Protocol, pytest, GitHub Actions.

---

## 2026-05-18 Acceptance Review: FAILED

Claude Code's previous attempt did **not** satisfy this plan. This section is mandatory reading before any further work.

The previous attempt failed for these concrete reasons:

- The core auto-launch bug was not fixed. In `geogebra_mcp_server.py`, daemon `ready` is still treated as equivalent to GeoGebra being connected, and `_call()` still only invokes `ensure_geogebra_running()` when `_ready` is not set. This is the same failure mode reported from Claude Code: daemon alive, GeoGebra closed, tool call fails, AI asks user to open GeoGebra manually.
- No false-ready regression test was added. Existing tests still pass because they do not cover the broken behavior.
- `python -m build --wheel` currently fails because `pyproject.toml` uses an invalid `[tool.setuptools.package-data]` key: `"" = [...]`.
- The package refactor was not completed. `geogebra_mcp/` exists only as a namespace-like directory with `__pycache__`; it does not contain `server.py`, `auto_launcher.py`, `doctor.py`, `__init__.py`, or packaged JS resources.
- `geogebra-mcp-doctor` was not implemented and no console script exists for it.
- `auto_launcher.py` still kills existing GeoGebra processes unconditionally. The required `GEOGEBRA_RESTART_EXISTING` opt-in safety gate is missing.
- `geogebra_daemon.js` still has no stable `GEOGEBRA_NOT_CONNECTED` marker and no `connect` handler.
- Structured MCP tools (`geogebra_run_commands`, `geogebra_create_construction`) were not implemented.
- CI still verifies only the old shallow wheel contents and does not smoke-test installed package resources.

**This is a hard failure, not a partial pass.** Passing the old `37` Python tests and `12` Node protocol tests is not enough. Those tests are currently too shallow and do not prove the user-facing problem is fixed.

### Non-Negotiable Instructions For Claude Code

- Do not claim completion because `python -m pytest -q` passes. The old tests passing proves only that old behavior was not broken.
- Do not skip Task 1. The false-ready regression test is the guardrail for the exact user-reported bug.
- Do not leave `pyproject.toml` in a state where `python -m build --wheel` fails.
- Do not create an empty `geogebra_mcp/` directory and call packaging complete. The package must contain importable runtime modules and JS resources.
- Do not leave automatic process killing as the default behavior. Existing GeoGebra sessions may contain unsaved work.
- Do not hand back for review until every command in the Final Verification Checklist has been run fresh and the outputs are reported.

### Required Repair Order

Follow this order exactly:

1. Complete Task 0 to document and cleanly address the failed previous attempt.
2. Complete Task 1 and prove the false-ready regression test fails before implementation.
3. Complete Task 2 and prove the same test passes after implementation.
4. Complete Task 3 before any manual end-to-end testing, so user data is protected.
5. Complete Task 4 and Task 7 before claiming packaging or PyPI readiness.
6. Complete Task 5 and Task 8 before claiming the tool is usable for non-expert users.
7. Only then complete Task 6 structured-tool improvements.

---

## 2026-05-18 Second Acceptance Review: FAILED

Claude Code's second attempt fixed several important items, but it still failed acceptance because the original user-facing scenario is not fully protected.

What improved in the second attempt:

- A real `geogebra_mcp/` package now exists with `server.py`, `auto_launcher.py`, `doctor.py`, JS resources, and `__init__.py`.
- `python -m build --wheel` succeeds.
- The wheel includes `geogebra_mcp/geogebra_daemon.js`, `geogebra_mcp/geogebra_bridge.js`, `geogebra_mcp/package.json`, and `geogebra_mcp/server.py`.
- `python -m pytest -q` passed after installing the declared dependencies: `47 passed`.
- Node protocol tests passed: `12 passed`.
- `GEOGEBRA_NOT_CONNECTED`, `connect`, and `GEOGEBRA_RESTART_EXISTING` now exist.
- `geogebra-mcp-doctor` exists and can run; it correctly reports `[FAIL] cdp_port` when GeoGebra is not currently listening on `localhost:9222`.

Why acceptance still failed:

- `geogebra_status` can still reproduce the original Claude Code failure. If the AI's first tool call is `geogebra_status`, and the daemon returns `{"connected": false}`, `_call("status")` updates `_connected=False` and returns the false status directly. It does **not** call `ensure_geogebra_running()`.
- This is not theoretical. The review used this simulation:

```bash
python -c "from geogebra_mcp.server import GeoGebraDaemonClient; import geogebra_mcp.server as s; c=GeoGebraDaemonClient(cdp_port=9222); c._ready.set(); c._connected=False; calls={'ensure':0}; c._write_request_once=lambda method, params=None, timeout=30: {'connected': False, 'error': 'GeoGebra 未运行或 CDP 端口不可用'}; s.ensure_geogebra_running=lambda port=None: calls.__setitem__('ensure', calls['ensure']+1) or True; print(c._call('status')); print('ensure_calls', calls['ensure'])"
```

It printed:

```text
{'connected': False, 'error': 'GeoGebra 未运行或 CDP 端口不可用'}
ensure_calls 0
```

That is a hard failure. Claude Code commonly checks status before drawing. If status returns `connected:false`, the AI may again tell the user to manually open GeoGebra. That is exactly the behavior this project is supposed to eliminate.

### New Non-Negotiable Requirement

`geogebra_status` must be part of the auto-launch path. A status call in lazy mode must not silently return `connected:false` on first use when GeoGebra is installed and can be launched.

Claude Code must not hand back again until there is a regression test proving:

- daemon `_ready` is set,
- `_connected` is false,
- `_write_request_once("status")` returns `{"connected": false}`,
- `_call("status")` calls `ensure_geogebra_running()`,
- the daemon restarts or reconnects,
- the final status is connected or the returned error clearly says auto-launch was attempted and failed.

### Updated Required Repair Order

Continue from the current implementation. Do not redo completed packaging work unless required by tests.

1. Complete **Task 2A** immediately.
2. Re-run the full verification checklist.
3. Perform the real Claude Code cold-start manual test.
4. Only then hand back for review.

---

## Current Problems and Risks

- Claude Code failure case: when GeoGebra is not open, MCP calls time out or return `connected: false`; the AI then asks the user to open GeoGebra manually.
- Likely root cause: `geogebra_daemon.js` emits a `type: "ready"` message even when `connected: false`; `geogebra_mcp_server.py` treats any ready message as `_ready.set()`, so `_call()` skips `ensure_geogebra_running()` because `_ready` is already set.
- Distribution risk: `python -m build --wheel` currently builds a wheel that contains Python modules but not `geogebra_daemon.js`, `geogebra_bridge.js`, `package.json`, or `package-lock.json`; `pip install geogebra-mcp` therefore cannot be trusted to run the daemon.
- Safety risk: `auto_launcher.ensure_geogebra_running()` kills existing GeoGebra processes automatically. This can close a user's unsaved GeoGebra work.
- Universality risk: MCP tool parameters use JSON strings (`commands_json`, `design_json`) instead of structured list/dict parameters, increasing tool-call friction for AI clients.
- Diagnostics risk: users cannot easily distinguish "GeoGebra not installed", "Node missing", "JS file missing", "npm dependencies missing", "CDP port blocked", and "GeoGebra opened without remote debugging".

---

## Files To Modify Or Create

- Modify: `geogebra_mcp_server.py`
  - Track daemon liveness separately from GeoGebra connection state.
  - Trigger auto-launch on GeoGebra connection failures.
  - Resolve packaged JS resources after package restructuring.
  - Add structured MCP tools while keeping old tools backward-compatible.

- Modify: `geogebra_daemon.js`
  - Emit clearer startup status.
  - Include machine-readable error codes for connection failures.
  - Add a lightweight `connect` handler so Python can force reconnect after launching GeoGebra.

- Modify: `auto_launcher.py`
  - Make killing existing GeoGebra instances opt-in.
  - Return structured launch diagnostics.
  - Improve Windows/macOS/Linux launch behavior and messages.

- Create: `geogebra_mcp/`
  - Move package runtime files here.
  - Include `__init__.py`, server modules, JS daemon, bridge, and package metadata resources.

- Create: `geogebra_mcp/doctor.py`
  - Provide `geogebra-mcp-doctor` CLI for local diagnostics.

- Modify: `pyproject.toml`
  - Switch from `py-modules` to packages.
  - Include JS/package resources in the wheel.
  - Add console script for doctor.
  - Fix mojibake in project description.

- Modify: `MANIFEST.in`
  - Keep source distribution aligned with packaged resources.

- Modify: `package.json`
  - Add name, version, scripts, and engine metadata.

- Modify: `README.md`
  - Clarify install paths for pip/source.
  - Add Claude Code/Codex MCP config examples.
  - Document auto-launch behavior and safe restart flag.
  - Add troubleshooting with `geogebra-mcp-doctor`.

- Modify: `.github/workflows/ci.yml`
  - Verify wheel contains JS resources.
  - Run import/resource lookup tests from installed wheel.

- Modify: `tests/test_auto_launcher.py`
  - Cover safe restart flag and structured diagnostics.

- Modify: `tests/test_mcp_server.py`
  - Cover the reported false-ready/connected-false case.
  - Cover structured tools.

- Create: `tests/test_packaging.py`
  - Assert package resources resolve from the wheel/package layout.

- Create: `tests/test_doctor.py`
  - Test diagnostic output without requiring real GeoGebra.

---

## Task 0: Repair The Failed Previous Attempt Baseline

**Files:**
- Inspect: `geogebra_mcp_server.py`
- Inspect: `auto_launcher.py`
- Inspect: `geogebra_daemon.js`
- Inspect: `pyproject.toml`
- Inspect: `geogebra_mcp/`
- Inspect: `tests/test_mcp_server.py`

- [ ] **Step 1: Confirm the previous attempt is currently failing**

Run:

```bash
python -m build --wheel
```

Expected current state before repair:

```text
FAILS with invalid pyproject.toml config: tool.setuptools.package-data
```

If this command unexpectedly passes, still continue with Step 2 because the auto-launch logic may remain wrong.

- [ ] **Step 2: Confirm the false-ready bug is still present before editing**

Inspect `geogebra_mcp_server.py` and verify whether these two patterns are still present:

```python
if resp.get('type') == 'ready':
    self._ready.set()
```

```python
if not self._ready.is_set():
    ensure_geogebra_running(...)
```

If both patterns exist, write this in the work log:

```text
Confirmed: daemon readiness is still conflated with GeoGebra connection state.
```

- [ ] **Step 3: Confirm the package refactor is incomplete**

Run:

```bash
python -c "import geogebra_mcp; print(geogebra_mcp); import geogebra_mcp.server"
```

Expected current state before repair:

```text
ModuleNotFoundError: No module named 'geogebra_mcp.server'
```

Do not treat the existence of `geogebra_mcp/__pycache__` as a package implementation.

- [ ] **Step 4: Confirm doctor command is missing**

Run:

```bash
geogebra-mcp-doctor
```

Expected current state before repair:

```text
command not found or not recognized
```

- [ ] **Step 5: Confirm unsafe process killing is still default**

Inspect `auto_launcher.py`. If `ensure_geogebra_running()` still calls `_kill_existing_geogebra()` without checking `GEOGEBRA_RESTART_EXISTING`, write this in the work log:

```text
Confirmed: existing GeoGebra processes are still killed by default.
```

- [ ] **Step 6: Do not patch around the failures**

Do not make a tiny `pyproject.toml` edit just to make build pass while leaving the package empty. The correct fix is Task 4: a real package with importable modules and included JS resources.

- [ ] **Step 7: Proceed to Task 1**

After recording the above, continue with Task 1. Do not skip directly to implementation without adding the regression test.

---

## Task 1: Reproduce The Auto-Launch Failure In Tests

**Files:**
- Modify: `tests/test_mcp_server.py`
- Modify: `geogebra_mcp_server.py`

- [ ] **Step 1: Add a failing unit test for the false-ready state**

Add a test that models the exact Claude Code failure: daemon process is alive, but GeoGebra is not connected. The test must prove that `ensure_geogebra_running()` is called on connection failure even when daemon startup already emitted `ready`.

Use this test shape in `tests/test_mcp_server.py`:

```python
def test_auto_launch_runs_when_daemon_ready_but_geogebra_disconnected():
    from geogebra_mcp_server import GeoGebraDaemonClient, DaemonError

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
        raise DaemonError("Cannot connect to GeoGebra: connection refused")

    client._write_request_once = fake_write_then_fail
    client._restart = fake_restart

    with patch("geogebra_mcp_server.ensure_geogebra_running", fake_ensure):
        with pytest.raises(DaemonError):
            client._call("status")

    assert calls["ensure"] == 1
    assert calls["restart"] == 1
```

If the existing `_call()` cannot be tested cleanly because write logic is embedded, first extract the single-attempt send/wait logic into `_write_request_once(method, params, timeout)`.

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m pytest tests/test_mcp_server.py::test_auto_launch_runs_when_daemon_ready_but_geogebra_disconnected -q
```

Expected before implementation:

```text
FAILED
```

The failure should show `ensure_geogebra_running()` was not called.

- [ ] **Step 3: Extract single-attempt request logic**

In `geogebra_mcp_server.py`, refactor `_call()` so the send/wait portion is isolated:

```python
def _write_request_once(self, method, params=None, timeout=30):
    with self._lock:
        self._next_id += 1
        msg_id = str(self._next_id)
        req = json.dumps({"id": msg_id, "method": method, "params": params or {}})
        self._pending[msg_id] = None
        try:
            self.proc.stdin.write(req + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            self._pending.pop(msg_id, None)
            raise DaemonError("Daemon crashed / 守护进程已崩溃")

    start = time.time()
    while time.time() - start < timeout:
        if self._pending.get(msg_id) is not None:
            resp = self._pending.pop(msg_id)
            if resp.get("ok"):
                return resp.get("result")
            raise DaemonError(resp.get("error", "Unknown error"))
        time.sleep(0.01)

    self._pending.pop(msg_id, None)
    raise DaemonError(f"Call timeout / 调用超时 '{method}' ({timeout}s)")
```

- [ ] **Step 4: Run the focused test again**

Run:

```bash
python -m pytest tests/test_mcp_server.py::test_auto_launch_runs_when_daemon_ready_but_geogebra_disconnected -q
```

Expected:

```text
FAILED
```

It should still fail until Task 2 changes connection-state handling.

- [ ] **Step 5: Commit the failing test and refactor**

Run:

```bash
git add geogebra_mcp_server.py tests/test_mcp_server.py
git commit -m "test: reproduce geogebra auto-launch connection failure"
```

---

## Task 2: Fix Daemon Ready Versus GeoGebra Connected State

**Files:**
- Modify: `geogebra_mcp_server.py`
- Modify: `geogebra_daemon.js`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Add connection state fields in Python**

In `GeoGebraDaemonClient.__init__`, keep `_ready` for daemon process readiness and add `_connected` for GeoGebra connection:

```python
self._ready = threading.Event()
self._connected = False
self._last_status = None
```

- [ ] **Step 2: Store connection state from daemon messages**

Update `_read_responses()` in `geogebra_mcp_server.py`:

```python
if resp.get("type") == "ready":
    self._last_status = resp
    self._connected = bool(resp.get("connected"))
    self._ready.set()
    continue
if resp.get("type") == "fatal":
    self._last_status = resp
    self._connected = False
    self._stderr_lines.append(f"FATAL: {resp.get('error')}")
    self._ready.set()
    continue
```

- [ ] **Step 3: Add a connection-error classifier**

Add this method to `GeoGebraDaemonClient`:

```python
def _looks_like_geogebra_connection_error(self, error: Exception) -> bool:
    text = str(error).lower()
    markers = [
        "cannot connect to geogebra",
        "unable to connect to geogebra",
        "无法连接到 geogebra",
        "connection refused",
        "ecconnrefused",
        "cdp",
        "not connected",
        "target closed",
        "websocket",
    ]
    return any(marker in text for marker in markers)
```

- [ ] **Step 4: Trigger auto-launch when GeoGebra is not connected**

Update `_call()` so it attempts launch when either `_connected` is false or the error looks like a GeoGebra connection failure:

```python
def _call(self, method, params=None, timeout=30):
    retried = False
    while True:
        try:
            result = self._write_request_once(method, params, timeout)
            if method == "status" and isinstance(result, dict):
                self._connected = bool(result.get("connected"))
                self._last_status = result
            else:
                self._connected = True
            return result
        except DaemonError as e:
            if retried:
                raise
            retried = True

            should_launch = (not self._connected) or self._looks_like_geogebra_connection_error(e)
            if should_launch:
                sys.stderr.write(
                    "[geogebra-mcp] GeoGebra not connected, attempting auto-launch... / 未连接，尝试自动启动...\n"
                )
                launched = ensure_geogebra_running(port=self.cdp_port)
                if launched:
                    sys.stderr.write(
                        "[geogebra-mcp] GeoGebra launch attempted, restarting daemon... / 已尝试启动，重启守护进程...\n"
                    )
                else:
                    sys.stderr.write(
                        "[geogebra-mcp] Auto-launch failed / 自动启动失败\n"
                    )

            sys.stderr.write(
                f"[geogebra-mcp] Daemon error ({e}), restarting... / 守护进程错误，正在重启...\n"
            )
            try:
                self._restart()
            except DaemonError as restart_err:
                raise DaemonError(f"Daemon restart failed / 守护进程重启失败: {restart_err}")
```

- [ ] **Step 5: Add a connect handler to the Node daemon**

In `geogebra_daemon.js`, add this handler:

```javascript
connect:    ()   => daemon.connect(),
```

Place it in the `handlers` object next to `status`.

- [ ] **Step 6: Make daemon connection errors machine-readable**

Change `ensureConnected()` error message in `geogebra_daemon.js` to include a stable marker:

```javascript
throw new Error(`GEOGEBRA_NOT_CONNECTED: Cannot connect to GeoGebra at ${BROWSER_URL}: ${result.error}. Start GeoGebra Classic 6 with --remote-debugging-port=${CDP_PORT}`);
```

- [ ] **Step 7: Run targeted tests**

Run:

```bash
python -m pytest tests/test_mcp_server.py tests/test_auto_launcher.py -q
node tests/test_daemon_protocol.js
```

Expected:

```text
all Python tests pass
12 tests: 12 passed, 0 failed
```

- [ ] **Step 8: Commit the auto-launch fix**

Run:

```bash
git add geogebra_mcp_server.py geogebra_daemon.js tests/test_mcp_server.py tests/test_auto_launcher.py
git commit -m "fix: auto-launch geogebra when daemon is ready but disconnected"
```

---

## Task 2A: Fix `geogebra_status` Cold-Start Auto-Launch

**This task was added after the second failed acceptance review. Do it before any remaining tasks.**

**Files:**
- Modify: `geogebra_mcp/server.py`
- Test: `tests/test_mcp_server.py`

**Problem:**
`_call("status")` currently returns `{"connected": false}` directly when the daemon is alive but GeoGebra is closed. That means `geogebra_status` can still make Claude Code ask the user to open GeoGebra manually. This is unacceptable.

- [ ] **Step 1: Add a failing regression test for status cold-start**

Add this test to `tests/test_mcp_server.py` near the existing auto-launch tests:

```python
def test_status_auto_launches_when_daemon_ready_but_status_disconnected():
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
```

- [ ] **Step 2: Run the new test before implementation and confirm it fails**

Run:

```bash
python -m pytest tests/test_mcp_server.py::test_status_auto_launches_when_daemon_ready_but_status_disconnected -q
```

Expected before implementation:

```text
FAILED
```

If it passes before implementation, the test is not actually covering the bug. Rewrite the test until it fails against the current code path.

- [ ] **Step 3: Implement status disconnected handling in `_call()`**

Update `_call()` in `geogebra_mcp/server.py` so a status result with `connected: false` is treated as a launchable connection failure on the first attempt.

The behavior must be:

```python
result = self._write_request_once(method, params, timeout)
if method == "status" and isinstance(result, dict):
    self._connected = bool(result.get("connected"))
    self._last_status = result
    if not self._connected and not retried:
        # Attempt auto-launch and retry status once.
        launched = ensure_geogebra_running(port=self.cdp_port)
        if launched:
            self._restart()
            retried = True
            continue
        return {
            **result,
            "auto_launch_attempted": True,
            "auto_launch_succeeded": False,
        }
    return result
```

Important details:

- Do not recurse infinitely.
- Retry status at most once after auto-launch/restart.
- Preserve useful status error text.
- Include `auto_launch_attempted` and `auto_launch_succeeded` when launch was attempted but failed.
- If launch succeeds and the second status is connected, return the connected status.

- [ ] **Step 4: Keep exception-based auto-launch behavior**

Do not break the existing exception path for `exec`, `batch`, `save`, and other non-status methods. `_looks_like_geogebra_connection_error()` should still trigger auto-launch on `GEOGEBRA_NOT_CONNECTED`.

- [ ] **Step 5: Fix misleading startup log**

In `main()` or equivalent startup code, do not print "Daemon connected to existing GeoGebra" merely because `_ready.is_set()`.

Use this logic:

```python
if _daemon._ready.is_set() and _daemon._connected:
    sys.stderr.write("[geogebra-mcp] Daemon connected to existing GeoGebra / 守护进程已连接\n")
elif _daemon._ready.is_set():
    sys.stderr.write("[geogebra-mcp] Daemon started but GeoGebra is not connected yet / 守护进程已启动，但 GeoGebra 尚未连接\n")
else:
    sys.stderr.write("[geogebra-mcp] Daemon started (waiting for GeoGebra on first use) / 守护进程已启动，等待首次使用\n")
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_mcp_server.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 7: Run the review simulation**

Run:

```bash
python -c "from geogebra_mcp.server import GeoGebraDaemonClient; import geogebra_mcp.server as s; c=GeoGebraDaemonClient(cdp_port=9222); c._ready.set(); c._connected=False; calls={'ensure':0,'restart':0,'attempt':0}; c._restart=lambda: (calls.__setitem__('restart', calls['restart']+1), setattr(c, '_connected', True)); s.ensure_geogebra_running=lambda port=None: calls.__setitem__('ensure', calls['ensure']+1) or True; c._write_request_once=lambda method, params=None, timeout=30: (calls.__setitem__('attempt', calls['attempt']+1) or ({'connected': False, 'error': 'GeoGebra 未运行或 CDP 端口不可用'} if calls['attempt']==1 else {'connected': True, 'title': 'GeoGebra Classic 6'})); print(c._call('status')); print(calls)"
```

Expected:

```text
{'connected': True, 'title': 'GeoGebra Classic 6'}
{'ensure': 1, 'restart': 1, 'attempt': 2}
```

- [ ] **Step 8: Commit**

Run:

```bash
git add geogebra_mcp/server.py tests/test_mcp_server.py
git commit -m "fix: auto-launch geogebra from disconnected status"
```

---

## Task 3: Make Existing GeoGebra Restart Safe And Opt-In

**Files:**
- Modify: `auto_launcher.py`
- Modify: `README.md`
- Test: `tests/test_auto_launcher.py`

- [ ] **Step 1: Add a restart policy helper**

Add to `auto_launcher.py`:

```python
def should_restart_existing_geogebra() -> bool:
    return os.environ.get("GEOGEBRA_RESTART_EXISTING", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
```

- [ ] **Step 2: Write tests for the restart policy**

Add to `tests/test_auto_launcher.py`:

```python
class TestRestartPolicy:
    def test_restart_disabled_by_default(self, clean_env):
        from auto_launcher import should_restart_existing_geogebra

        assert should_restart_existing_geogebra() is False

    def test_restart_enabled_with_env_flag(self, clean_env):
        from auto_launcher import should_restart_existing_geogebra

        os.environ["GEOGEBRA_RESTART_EXISTING"] = "1"
        assert should_restart_existing_geogebra() is True
```

- [ ] **Step 3: Change `ensure_geogebra_running()` to avoid killing by default**

Replace unconditional kill calls with guarded calls:

```python
if should_restart_existing_geogebra():
    _kill_existing_geogebra()
    time.sleep(1.5)
```

Apply the same guard in the retry block:

```python
if should_restart_existing_geogebra():
    _kill_existing_geogebra()
    time.sleep(1.0)
```

- [ ] **Step 4: Add a test that kill is skipped by default**

Add:

```python
@patch("auto_launcher._kill_existing_geogebra")
@patch("auto_launcher.find_geogebra_installation")
@patch("auto_launcher.is_cdp_ready")
def test_does_not_kill_existing_geogebra_by_default(self, mock_ready, mock_find, mock_kill, clean_env):
    mock_ready.return_value = False
    mock_find.return_value = None

    assert ensure_geogebra_running(port=9222) is False
    mock_kill.assert_not_called()
```

- [ ] **Step 5: Add a test that kill happens when explicitly enabled**

Add:

```python
@patch("auto_launcher._kill_existing_geogebra")
@patch("auto_launcher.find_geogebra_installation")
@patch("auto_launcher.is_cdp_ready")
def test_kills_existing_geogebra_when_env_enabled(self, mock_ready, mock_find, mock_kill, clean_env):
    os.environ["GEOGEBRA_RESTART_EXISTING"] = "1"
    mock_ready.return_value = False
    mock_find.return_value = None

    assert ensure_geogebra_running(port=9222) is False
    mock_kill.assert_called_once()
```

- [ ] **Step 6: Document the safety behavior**

Add to `README.md` troubleshooting:

````markdown
### Auto-launch safety

By default, GeoGebra MCP will not kill an already running GeoGebra process. If GeoGebra is already open without `--remote-debugging-port`, save your work and restart it manually, or opt in to automatic restart:

```bash
set GEOGEBRA_RESTART_EXISTING=1      # Windows
export GEOGEBRA_RESTART_EXISTING=1   # macOS/Linux
```
````

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_auto_launcher.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 8: Commit**

Run:

```bash
git add auto_launcher.py tests/test_auto_launcher.py README.md
git commit -m "fix: make geogebra restart opt-in"
```

---

## Task 4: Convert To A Real Python Package And Include JS Resources

**Files:**
- Create: `geogebra_mcp/__init__.py`
- Move: `geogebra_mcp_server.py` -> `geogebra_mcp/server.py`
- Move: `auto_launcher.py` -> `geogebra_mcp/auto_launcher.py`
- Move: `geogebra_api.py` -> `geogebra_mcp/api.py`
- Move: `geogebra_bridge.py` -> `geogebra_mcp/bridge.py`
- Move: `install_wizard.py` -> `geogebra_mcp/install_wizard.py`
- Move: `geogebra_daemon.js` -> `geogebra_mcp/geogebra_daemon.js`
- Move: `geogebra_bridge.js` -> `geogebra_mcp/geogebra_bridge.js`
- Copy or move: `package.json` -> `geogebra_mcp/package.json`
- Copy or move: `package-lock.json` -> `geogebra_mcp/package-lock.json`
- Modify: `pyproject.toml`
- Modify: `MANIFEST.in`
- Modify: tests imports

- [ ] **Step 1: Create package directory**

Run:

```bash
mkdir geogebra_mcp
```

Create `geogebra_mcp/__init__.py`:

```python
"""GeoGebra MCP package."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Move runtime modules into the package**

Move files as listed above. Keep thin compatibility wrappers at the repository root for one release.

Root `geogebra_mcp_server.py` should become:

```python
"""Backward-compatible entrypoint for geogebra_mcp.server."""

from geogebra_mcp.server import *  # noqa: F401,F403
from geogebra_mcp.server import main


if __name__ == "__main__":
    main()
```

Root `auto_launcher.py` should become:

```python
"""Backward-compatible imports for geogebra_mcp.auto_launcher."""

from geogebra_mcp.auto_launcher import *  # noqa: F401,F403
```

- [ ] **Step 3: Update imports**

In `geogebra_mcp/server.py`, replace:

```python
from auto_launcher import (
    ensure_geogebra_running,
    get_cdp_port,
)
```

with:

```python
from .auto_launcher import (
    ensure_geogebra_running,
    get_cdp_port,
)
```

- [ ] **Step 4: Resolve JS resources from package files**

In `geogebra_mcp/server.py`:

```python
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DAEMON_JS = os.path.join(PACKAGE_DIR, "geogebra_daemon.js")
```

In `geogebra_mcp/api.py`:

```python
BRIDGE_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geogebra_bridge.js")
```

- [ ] **Step 5: Update `pyproject.toml` package config**

Replace `[tool.setuptools] py-modules = ...` with:

```toml
[project]
description = "MCP Server for controlling GeoGebra Classic 6 and drawing animated mechanisms via AI"

[project.scripts]
geogebra-mcp-server = "geogebra_mcp.server:main"
geogebra-mcp-doctor = "geogebra_mcp.doctor:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["geogebra_mcp*"]

[tool.setuptools.package-data]
geogebra_mcp = [
    "geogebra_daemon.js",
    "geogebra_bridge.js",
    "package.json",
    "package-lock.json",
]
```

Keep all existing dependencies, classifiers, URLs, and optional dependencies.

- [ ] **Step 6: Update `MANIFEST.in`**

Use:

```text
include LICENSE
include README.md
include requirements.txt
include geogebra_mcp/geogebra_daemon.js
include geogebra_mcp/geogebra_bridge.js
include geogebra_mcp/package.json
include geogebra_mcp/package-lock.json
recursive-include tests *.py *.js
```

- [ ] **Step 7: Update tests imports**

Tests that import `auto_launcher` may keep using compatibility wrappers for now, but add at least one direct package import test:

```python
def test_package_imports_server():
    import geogebra_mcp.server as server

    assert server.__version__ == "0.1.0"
```

- [ ] **Step 8: Build and verify wheel contents**

Run:

```bash
python -m build --wheel
python -c "import glob, zipfile; wheel=glob.glob('dist/*.whl')[-1]; names=zipfile.ZipFile(wheel).namelist(); print('\n'.join(names)); assert any(n.endswith('geogebra_mcp/geogebra_daemon.js') for n in names); assert any(n.endswith('geogebra_mcp/package.json') for n in names)"
```

Expected:

```text
no assertion error
```

- [ ] **Step 9: Run full tests**

Run:

```bash
python -m pytest -q
node tests/test_daemon_protocol.js
```

Expected:

```text
all Python tests pass
12 tests: 12 passed, 0 failed
```

- [ ] **Step 10: Commit**

Run:

```bash
git add geogebra_mcp geogebra_mcp_server.py auto_launcher.py pyproject.toml MANIFEST.in tests
git commit -m "build: package geogebra mcp runtime resources"
```

---

## Task 5: Add `geogebra-mcp-doctor` Diagnostics

**Files:**
- Create: `geogebra_mcp/doctor.py`
- Modify: `pyproject.toml`
- Create: `tests/test_doctor.py`
- Modify: `README.md`

- [ ] **Step 1: Create doctor module**

Create `geogebra_mcp/doctor.py`:

```python
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


def _run_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return str(exc)
    return (result.stdout or result.stderr).strip()


def run_checks() -> list[CheckResult]:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_js = os.path.join(package_dir, "geogebra_daemon.js")
    package_json = os.path.join(package_dir, "package.json")
    node = shutil.which("node")
    npm = shutil.which("npm")
    geogebra_path = find_geogebra_installation()
    port = get_cdp_port()

    checks = [
        CheckResult("python", sys.version_info >= (3, 10), sys.version.split()[0]),
        CheckResult("node", node is not None, node or "node not found on PATH"),
        CheckResult("npm", npm is not None, npm or "npm not found on PATH"),
        CheckResult("daemon_js", os.path.exists(daemon_js), daemon_js),
        CheckResult("package_json", os.path.exists(package_json), package_json),
        CheckResult("geogebra_install", geogebra_path is not None, geogebra_path or "GeoGebra Classic 6 not found"),
        CheckResult("cdp_port", is_cdp_ready(port=port), f"localhost:{port}"),
    ]

    if node:
        checks.append(CheckResult("node_version", True, _run_version(["node", "--version"])))
    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines = ["GeoGebra MCP doctor"]
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    if not all(check.ok for check in checks):
        lines.append("")
        lines.append("If cdp_port fails, start GeoGebra Classic 6 with --remote-debugging-port or let the MCP server auto-launch it.")
        lines.append("If daemon_js or package_json fails, reinstall the package from a fixed wheel or run from source.")
    return "\n".join(lines)


def main() -> None:
    checks = run_checks()
    print(format_checks(checks))
    raise SystemExit(0 if all(check.ok for check in checks) else 1)
```

- [ ] **Step 2: Add tests**

Create `tests/test_doctor.py`:

```python
from geogebra_mcp.doctor import CheckResult, format_checks


def test_format_checks_success():
    output = format_checks([CheckResult("python", True, "3.12")])
    assert "[OK] python: 3.12" in output


def test_format_checks_failure_includes_hint():
    output = format_checks([CheckResult("cdp_port", False, "localhost:9222")])
    assert "[FAIL] cdp_port: localhost:9222" in output
    assert "--remote-debugging-port" in output
```

- [ ] **Step 3: Ensure script entry exists**

Confirm `pyproject.toml` includes:

```toml
geogebra-mcp-doctor = "geogebra_mcp.doctor:main"
```

- [ ] **Step 4: Document doctor usage**

Add to `README.md`:

````markdown
## Diagnostics

Run:

```bash
geogebra-mcp-doctor
```

It checks Python, Node.js, npm, packaged daemon files, GeoGebra installation detection, and the configured CDP port.
````

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_doctor.py -q
python -m pytest -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Commit**

Run:

```bash
git add geogebra_mcp/doctor.py tests/test_doctor.py pyproject.toml README.md
git commit -m "feat: add geogebra mcp doctor command"
```

---

## Task 6: Add Structured MCP Tools While Keeping Backward Compatibility

**Files:**
- Modify: `geogebra_mcp/server.py`
- Test: `tests/test_mcp_server.py`
- Modify: `README.md`

- [ ] **Step 1: Add structured batch tool**

Keep existing `geogebra_batch(commands_json: str)` unchanged for compatibility. Add:

```python
@mcp.tool()
async def geogebra_run_commands(commands: list[str]) -> str:
    """
    Execute multiple GeoGebra commands from a structured list.

    Args:
        commands: Ordered GeoGebra commands, for example ["A=(0,0)", "B=(6,0)", "Segment(A,B)"].
    """
    try:
        if not isinstance(commands, list) or not all(isinstance(cmd, str) for cmd in commands):
            return json.dumps({"success": False, "error": "commands must be a list of strings"}, ensure_ascii=False)
        results = get_daemon().batch(commands)
        ok = sum(1 for r in results if r["result"] not in (False, None) and not str(r["result"]).startswith("Error"))
        return json.dumps({"success": True, "total": len(results), "succeeded": ok, "failed": len(results) - ok, "details": results}, ensure_ascii=False)
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
```

- [ ] **Step 2: Add structured mechanism tool**

Keep `geogebra_draw_mechanism(name: str, design_json: str, output_dir: str = "")`. Add:

```python
@mcp.tool()
async def geogebra_create_construction(name: str, design: dict, output_dir: str = "") -> str:
    """
    Create a construction from a structured design dictionary.

    Args:
        name: Output filename stem.
        design: Dict with perspective, commands, styles, animate, and speed.
        output_dir: Output directory.
    """
    return await _create_construction_from_design(name=name, design=design, output_dir=output_dir)
```

Extract shared implementation from `geogebra_draw_mechanism()`:

```python
async def _create_construction_from_design(name: str, design: dict, output_dir: str = "") -> str:
    if not isinstance(design, dict):
        return json.dumps({"success": False, "error": "design must be an object"}, ensure_ascii=False)
    if not isinstance(design.get("commands", []), list):
        return json.dumps({"success": False, "error": "design.commands must be a list"}, ensure_ascii=False)
    # Move the existing implementation body here, starting after json.loads().
```

Then make `geogebra_draw_mechanism()` call it:

```python
design = json.loads(design_json)
return await _create_construction_from_design(name=name, design=design, output_dir=output_dir)
```

- [ ] **Step 3: Add tests for validation**

Add:

```python
def test_structured_commands_rejects_non_list():
    # Test the validation branch directly if FastMCP wrapping makes direct invocation hard.
    commands = "A=(0,0)"
    assert not isinstance(commands, list)
```

If direct async tool calls are available, use:

```python
@pytest.mark.asyncio
async def test_geogebra_run_commands_rejects_non_list():
    from geogebra_mcp.server import geogebra_run_commands

    result = await geogebra_run_commands("A=(0,0)")
    parsed = json.loads(result)
    assert parsed["success"] is False
```

- [ ] **Step 4: Update README tool table**

Add rows:

```markdown
| `geogebra_run_commands` | Structured list version of batch command execution. Preferred for AI clients. |
| `geogebra_create_construction` | Structured dict version of one-step construction creation. Preferred for AI clients. |
```

Mark old JSON-string tools as backward compatible:

```markdown
`geogebra_batch` and `geogebra_draw_mechanism` remain available for older clients, but new clients should prefer structured tools.
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_mcp_server.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Commit**

Run:

```bash
git add geogebra_mcp/server.py tests/test_mcp_server.py README.md
git commit -m "feat: add structured geogebra mcp tools"
```

---

## Task 7: Strengthen CI And Packaging Verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_packaging.py`

- [ ] **Step 1: Add package resource test**

Create `tests/test_packaging.py`:

```python
import os

import geogebra_mcp.server as server


def test_daemon_js_resource_exists():
    assert os.path.exists(server.DAEMON_JS)
    assert server.DAEMON_JS.endswith("geogebra_daemon.js")
```

- [ ] **Step 2: Fix CI wheel verification**

In `.github/workflows/ci.yml`, update the wheel check:

```yaml
- name: Verify wheel contents
  run: |
    python -c "
    import zipfile, glob
    wheel = glob.glob('dist/*.whl')[0]
    names = zipfile.ZipFile(wheel).namelist()
    print('\n'.join(names))
    assert any(n.endswith('geogebra_mcp/geogebra_daemon.js') for n in names), 'Missing geogebra_daemon.js'
    assert any(n.endswith('geogebra_mcp/geogebra_bridge.js') for n in names), 'Missing geogebra_bridge.js'
    assert any(n.endswith('geogebra_mcp/package.json') for n in names), 'Missing package.json'
    assert any(n.endswith('geogebra_mcp/server.py') for n in names), 'Missing server.py'
    print('OK: Wheel contains required runtime files')
    "
```

- [ ] **Step 3: Add installed wheel smoke test in CI**

Add after wheel verification:

```yaml
- name: Smoke test installed wheel
  run: |
    python -m venv /tmp/geogebra-mcp-smoke
    /tmp/geogebra-mcp-smoke/bin/python -m pip install dist/*.whl
    /tmp/geogebra-mcp-smoke/bin/python -c "import os, geogebra_mcp.server as s; assert os.path.exists(s.DAEMON_JS); print(s.DAEMON_JS)"
```

- [ ] **Step 4: Run local checks**

Run:

```bash
python -m pytest tests/test_packaging.py -q
python -m build --wheel
```

Expected:

```text
test passes
wheel builds successfully
```

- [ ] **Step 5: Commit**

Run:

```bash
git add .github/workflows/ci.yml tests/test_packaging.py
git commit -m "ci: verify packaged geogebra runtime resources"
```

---

## Task 8: End-To-End Manual Verification With Claude Code Scenario

**Files:**
- Modify: `README.md`
- No code changes unless verification reveals a defect.

- [ ] **Step 1: Start from GeoGebra closed**

Close GeoGebra Classic 6. Make sure no `GeoGebra.exe` / `geogebra` process is running.

- [ ] **Step 2: Run doctor**

Run:

```bash
geogebra-mcp-doctor
```

Expected when GeoGebra is closed:

```text
[OK] daemon_js
[OK] package_json
[OK] geogebra_install
[FAIL] cdp_port: localhost:9222
```

This is acceptable before auto-launch.

- [ ] **Step 3: Start MCP server manually**

Run:

```bash
geogebra-mcp-server
```

Expected stderr should include:

```text
Lazy mode
Daemon started
```

It must not require GeoGebra to already be open.

- [ ] **Step 4: In Claude Code, call the tool with GeoGebra closed**

Ask Claude Code:

```text
画一个曲柄摇杆机构，并保存 ggb 和 png
```

Expected behavior:

- MCP server attempts auto-launch.
- GeoGebra Classic 6 opens with the configured CDP port.
- Tool call continues after daemon restart/reconnect.
- Claude Code does not ask the user to manually open GeoGebra.
- A `.ggb` and `.png` file are saved.

- [ ] **Step 5: Verify status after the tool call**

Call `geogebra_status`.

Expected JSON:

```json
{
  "connected": true
}
```

Additional fields such as `title` and `objectCount` may be present.

- [ ] **Step 6: Document successful manual verification**

Add a short note to `README.md`:

```markdown
### Expected first-use behavior

If GeoGebra is installed but closed, the first MCP tool call should auto-launch GeoGebra Classic 6 with the configured CDP port and retry the daemon connection. If this fails, run `geogebra-mcp-doctor` and check the troubleshooting section.
```

- [ ] **Step 7: Commit docs**

Run:

```bash
git add README.md
git commit -m "docs: document first-use auto-launch behavior"
```

---

## Final Verification Checklist

- [ ] `python -m pytest -q` passes.
- [ ] `node tests/test_daemon_protocol.js` passes.
- [ ] `python -m build --wheel` succeeds.
- [ ] `python -c "import geogebra_mcp.server as s; print(s.DAEMON_JS)"` succeeds.
- [ ] `python -m pytest tests/test_mcp_server.py::test_status_auto_launches_when_daemon_ready_but_status_disconnected -q` passes.
- [ ] Status cold-start simulation shows `ensure_geogebra_running()` called once and status retried once.
- [ ] Wheel contains:
  - `geogebra_mcp/geogebra_daemon.js`
  - `geogebra_mcp/geogebra_bridge.js`
  - `geogebra_mcp/package.json`
  - `geogebra_mcp/server.py`
- [ ] Installed wheel smoke test succeeds in a clean virtual environment.
- [ ] `geogebra-mcp-doctor` runs after installing the wheel.
- [ ] `geogebra-mcp-server` starts in lazy mode when GeoGebra is closed.
- [ ] First MCP tool call auto-launches GeoGebra instead of asking the user to open it manually.
- [ ] Existing GeoGebra processes are not killed unless `GEOGEBRA_RESTART_EXISTING=1`.
- [ ] Claude Code can draw a crank-rocker mechanism from a cold start.
- [ ] `README.md`, `CHANGELOG.md`, and `pyproject.toml` do not contain mojibake such as `鈥?` or `бк`.

---

## Automatic Rejection Criteria

The next review must reject the work immediately if any of these are true:

- `python -m build --wheel` fails.
- `import geogebra_mcp.server` fails.
- `geogebra-mcp-doctor` is missing.
- `tests/test_mcp_server.py` does not include a regression test for daemon-ready-but-GeoGebra-disconnected behavior.
- `tests/test_mcp_server.py` does not include a regression test for status-returned `connected:false` triggering auto-launch.
- `geogebra_mcp_server.py` still triggers auto-launch only when `_ready` is unset.
- `geogebra_mcp/server.py` returns `{"connected": false}` from `_call("status")` without attempting auto-launch.
- startup logging says "connected to existing GeoGebra" when `_ready=True` but `_connected=False`.
- `auto_launcher.py` still calls `_kill_existing_geogebra()` by default.
- The wheel does not contain `geogebra_mcp/geogebra_daemon.js`.
- Claude Code reports "please open GeoGebra manually" during the cold-start manual test.
- The final handoff says "tests pass" without showing build, wheel, import, doctor, and cold-start evidence.

---

## Handoff Notes For Claude Code

Implement in task order. The previous attempt failed because it did not implement the core logic, did not add the required regression test, left packaging broken, and relied on old tests that do not cover the bug. Do not repeat that pattern.

Do not skip the failing test in Task 1; it protects against the exact user-facing failure. Prefer small commits after each task. If package restructuring creates import churn, keep root compatibility wrappers so existing users running `python geogebra_mcp_server.py` are not broken immediately.

When handing the branch back, include:

- A short summary of how daemon liveness is now separated from GeoGebra connection state.
- The exact regression test name that fails before the fix and passes after the fix.
- The exact status cold-start regression test name and output.
- The exact status cold-start simulation output showing `ensure=1`, `restart=1`, and `attempt=2`.
- The exact files moved into `geogebra_mcp/`.
- The exact wheel content check output showing JS files are included.
- The exact safety behavior for `GEOGEBRA_RESTART_EXISTING`.
- The exact result of a cold-start Claude Code/GeoGebra manual test, including whether GeoGebra was closed at the beginning.

After completing all tasks, hand the branch back for review with:

```bash
git status --short
python -m pytest -q
node tests/test_daemon_protocol.js
python -m build --wheel
python -c "import geogebra_mcp.server as s; print(s.DAEMON_JS)"
python -m pytest tests/test_mcp_server.py::test_status_auto_launches_when_daemon_ready_but_status_disconnected -q
python -c "from geogebra_mcp.server import GeoGebraDaemonClient; import geogebra_mcp.server as s; c=GeoGebraDaemonClient(cdp_port=9222); c._ready.set(); c._connected=False; calls={'ensure':0,'restart':0,'attempt':0}; c._restart=lambda: (calls.__setitem__('restart', calls['restart']+1), setattr(c, '_connected', True)); s.ensure_geogebra_running=lambda port=None: calls.__setitem__('ensure', calls['ensure']+1) or True; c._write_request_once=lambda method, params=None, timeout=30: (calls.__setitem__('attempt', calls['attempt']+1) or ({'connected': False, 'error': 'GeoGebra 未运行或 CDP 端口不可用'} if calls['attempt']==1 else {'connected': True, 'title': 'GeoGebra Classic 6'})); print(c._call('status')); print(calls)"
python -c "import glob, zipfile; wheel=glob.glob('dist/*.whl')[-1]; names=zipfile.ZipFile(wheel).namelist(); assert any(n.endswith('geogebra_mcp/geogebra_daemon.js') for n in names); assert any(n.endswith('geogebra_mcp/package.json') for n in names); print('wheel ok')"
geogebra-mcp-doctor
```
