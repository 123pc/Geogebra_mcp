---
name: geogebra-setup
description: Automate installation and global configuration of this GeoGebra MCP project for Claude Code, Codex, and other local AI agents. Use when the user asks to set up, install, configure, bootstrap, or register GeoGebra MCP after cloning the repository. Web Runtime is the default — no GeoGebra desktop install needed.
---

# GeoGebra Setup

Set up GeoGebra MCP from a freshly cloned repository so the user does not need to hand-edit MCP JSON/TOML files.

## Workflow

1. Confirm you are in the GeoGebra MCP repository root. It should contain `pyproject.toml`, `package.json`, `geogebra_mcp/`, and `scripts/setup_geogebra_mcp.py`.
2. Ask the user which AI agent(s) to configure. Present the options in natural language:
   - Claude Code
   - Codex
   - Both (default)

   For example: "Which AI agent would you like me to set up GeoGebra MCP for? Claude Code, Codex, or both?" Wait for the user's response before proceeding.

3. Run the setup script with the appropriate `--agent` flag based on the user's choice:
   - Claude Code only: `python scripts/setup_geogebra_mcp.py --agent claude`
   - Codex only: `python scripts/setup_geogebra_mcp.py --agent codex`
   - Both: `python scripts/setup_geogebra_mcp.py --agent all`
4. If dependencies are already installed, pass `--skip-deps`.
5. If the environment blocks network or package installation, request approval and rerun the same script.
6. Treat `geogebra-mcp-doctor` returning non-zero as acceptable when the only failing check is `cdp_port`; GeoGebra may be closed until the first MCP tool call.
7. Tell the user to restart their agent session after setup writes global config.
8. Verify in a new session by asking the agent to check GeoGebra status and draw a small construction.

## What The Script Does

The setup script:

- Runs `npm install` (installs Puppeteer + Chromium for Web Runtime).
- Runs `python -m pip install -e .`.
- The default runtime is Web Runtime, which launches Chromium and loads GeoGebra Web — no Classic 6 install needed.
- Writes Claude Code MCP config to `~/.claude/.mcp.json`.
- Adds `geogebra` to Claude Code `~/.claude/settings.json` allowlist.
- Writes a managed Codex MCP block to `~/.codex/config.toml`.
- Copies bundled skills into common skill roots:
  - `~/.codex/skills`
  - `~/.agents/skills`
  - `~/.claude/skills`
- Runs `python -m geogebra_mcp.doctor`.

The MCP command uses the current Python executable with:

```bash
python -m geogebra_mcp.server
```

This avoids relying on console script PATH visibility after installation.

## Updating

To update an existing installation to the latest version, run from the project directory:

```bash
python update.py
```

This pulls the latest `main` branch, reinstalls dependencies, and syncs MCP config and skills without re-cloning.

## Verification Prompt

After restarting the agent, ask:

```text
Use GeoGebra MCP to check status and draw a triangle.
```

Pass criteria:

- The agent can see or call the `geogebra` MCP server.
- `geogebra_status` runs.
- If GeoGebra is closed, the server attempts auto-launch.
- A simple construction can be created with `geogebra_run_commands` or `geogebra_create_construction`.

## Troubleshooting

If setup fails during `npm install`, install Node.js/npm or rerun with network permission.

If setup fails during `pip install -e .`, verify Python 3.10+ and pip are available.

If Claude Code still cannot see the server, inspect:

```text
~/.claude/.mcp.json
~/.claude/settings.json
```

If Codex still cannot see the server, inspect:

```text
~/.codex/config.toml
```

If GeoGebra cannot connect, run:

```bash
python -m geogebra_mcp.doctor
```

For desktop backend only: if only `cdp_port` fails, start with a normal MCP tool call first; auto-launch should handle it. If `geogebra_install` fails, install GeoGebra Classic 6 desktop edition. For Web Runtime (default), `geogebra_install` and `cdp_port` are skipped — check `web_assets` and `puppeteer` instead.
