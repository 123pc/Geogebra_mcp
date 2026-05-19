---
name: use-geogebra-mcp
description: Use when a user mentions use_geogebra_mcp or wants Claude Code, Codex, or another MCP-capable AI agent to set up, diagnose, or use the GeoGebra MCP server to control GeoGebra Classic 6, draw geometry, plot functions, build animated mechanisms, save .ggb files, or export PNG screenshots.
metadata:
  short-description: Use GeoGebra MCP from AI agents
---

# Use GeoGebra MCP

Use this skill when the user wants an AI coding agent to operate GeoGebra through this project's MCP server. The intended path is:

```text
AI agent -> MCP stdio -> Python geogebra-mcp-server -> Node daemon -> GeoGebra Classic 6 CDP -> ggbApplet API
```

## Core Rules

- Prefer the installed console command `geogebra-mcp-server`; use `python <repo>/geogebra_mcp_server.py` as the source-tree fallback.
- Prefer structured MCP tools: `geogebra_run_commands` and `geogebra_create_construction`.
- Use legacy JSON-string tools only for older clients: `geogebra_batch` and `geogebra_draw_mechanism`.
- `geogebra_status` is safe as a first call: if GeoGebra is closed, the server should attempt auto-launch.
- Do not ask the user to manually open GeoGebra until auto-launch and diagnostics have been attempted.
- Do not kill an already-open GeoGebra session by default. Only set `GEOGEBRA_RESTART_EXISTING=1` after the user confirms their GeoGebra work is saved.

## Setup From Source

From the repository root:

For MATLAB Agentic Toolkit style automated setup, prefer:

```bash
python scripts/setup_geogebra_mcp.py
```

This installs dependencies, writes common global MCP client config, copies bundled skills, and runs diagnostics.

Manual setup:

```bash
npm install
python -m pip install -e .
geogebra-mcp-doctor
```

Expected `geogebra-mcp-doctor` behavior:

- `[OK] daemon_js` and `[OK] package_json` mean package resources are present.
- `[OK] geogebra_install` means GeoGebra Classic 6 was found.
- `[FAIL] cdp_port: localhost:9222` is acceptable if GeoGebra is currently closed; the first MCP tool call should auto-launch it.

If `geogebra-mcp-doctor` is missing, install the package first:

```bash
python -m pip install -e .
```

If Node dependencies are missing, run:

```bash
npm install
```

## Configure An MCP Client

For Claude Code or another stdio MCP client, prefer the installed command:

```json
{
  "mcpServers": {
    "geogebra": {
      "command": "geogebra-mcp-server",
      "args": []
    }
  }
}
```

Source-tree fallback:

```json
{
  "mcpServers": {
    "geogebra": {
      "command": "python",
      "args": ["D:/project/Geogebra_mcp/geogebra_mcp_server.py"]
    }
  }
}
```

If the client has an allowlist such as Claude Code `settings.json`, enable the server name:

```json
"enabledMcpjsonServers": ["geogebra"]
```

Restart the MCP client after changing configuration.

## Environment Variables

Default CDP port:

```bash
GEOGEBRA_CDP_PORT=9222
```

Use a custom port only if all sides agree: MCP server environment, GeoGebra launch flag, and diagnostics.

Safe restart flag:

```bash
GEOGEBRA_RESTART_EXISTING=1
```

Only use this when the user has saved existing GeoGebra work. Without this flag, the server should not kill an existing GeoGebra process.

## First-Use Workflow

When asked to draw or plot with GeoGebra:

1. Call `geogebra_status`.
2. If status returns connected, proceed.
3. If status reports disconnected but includes auto-launch metadata, inspect it:
   - `auto_launch_attempted: true`
   - `auto_launch_succeeded: false`
   Then run `geogebra-mcp-doctor` or ask the user for the doctor output.
4. For command reference, call `geogebra_help(topic="commands")` or `geogebra_help(topic="mechanisms")`.
5. Use `geogebra_new_construction` before creating a fresh drawing.
6. Use `geogebra_run_commands` for command lists.
7. Use `geogebra_set_appearance` for colors, line thickness, point size, visibility, and labels.
8. Use `geogebra_animate` for sliders.
9. Use `geogebra_save` and `geogebra_export_png` for outputs.

## Preferred Tool Patterns

### General command batch

Use `geogebra_run_commands` with a list of strings:

```json
{
  "commands": [
    "A = (0, 0)",
    "B = (6, 0)",
    "Segment(A, B)"
  ]
}
```

### Complete construction

Use `geogebra_create_construction` with a structured design:

```json
{
  "name": "crank_rocker",
  "output_dir": "D:/output",
  "design": {
    "perspective": "G",
    "animate": "alpha",
    "speed": 0.5,
    "commands": [
      "O1 = (0, 0)",
      "O2 = (6, 0)",
      "alpha = 45 deg",
      "A = O1 + (2*cos(alpha), 2*sin(alpha))",
      "c1 = Circle(A, 5)",
      "c2 = Circle(O2, 4)",
      "B = Intersect(c1, c2, 1)",
      "Segment(O1, A)",
      "Segment(A, B)",
      "Segment(B, O2)"
    ],
    "styles": [
      {"label": "A", "color": [1, 0, 0], "point_size": 5},
      {"label": "B", "color": [0, 0, 1], "point_size": 5}
    ]
  }
}
```

Prefer ASCII labels like `alpha` when cross-client encoding is uncertain. Use Greek letters only when the client and GeoGebra command encoding are known to be stable.

## Example User Requests

Useful prompts the AI agent should be able to handle:

- "Use GeoGebra MCP to draw a crank-rocker mechanism, animate it, and save .ggb and PNG outputs."
- "Plot y=sin(x) and y=cos(x) in GeoGebra with different colors and export a screenshot."
- "Create a triangle construction with perpendicular bisectors and circumcircle."
- "Check whether GeoGebra MCP is installed and diagnose why it is not connecting."

## Troubleshooting

If the MCP client says GeoGebra is disconnected:

1. Run `geogebra-mcp-doctor`.
2. If only `cdp_port` fails and GeoGebra is closed, try a first MCP tool call again; auto-launch should open GeoGebra.
3. If `geogebra_install` fails, install GeoGebra Classic 6 desktop edition.
4. If `node` or `npm` fails, install Node.js and rerun `npm install`.
5. If `daemon_js` or `package_json` fails, reinstall the Python package or run from the source repository.
6. If GeoGebra is already open but not controllable, ask the user to save their work. Then either close GeoGebra manually or set `GEOGEBRA_RESTART_EXISTING=1` and retry.

If the first `geogebra_status` returns `connected:false` without any auto-launch attempt, the server is outdated. Update to a version that includes status cold-start auto-launch.

## Verification Checklist

Before claiming setup is complete, run:

```bash
python -m pytest -q
node tests/test_daemon_protocol.js
python -m build --wheel
python -c "import geogebra_mcp.server as s; print(s.DAEMON_JS)"
python -c "import glob, zipfile; wheel=glob.glob('dist/*.whl')[-1]; names=zipfile.ZipFile(wheel).namelist(); assert any(n.endswith('geogebra_mcp/geogebra_daemon.js') for n in names); assert any(n.endswith('geogebra_mcp/package.json') for n in names); print('wheel ok')"
geogebra-mcp-doctor
```

Then perform one real cold-start test:

1. Close GeoGebra.
2. Ask the MCP client: "Draw a crank-rocker mechanism in GeoGebra and save .ggb and PNG outputs."
3. Pass only if GeoGebra opens automatically, the drawing is created, and the files are saved without asking the user to manually open GeoGebra.
