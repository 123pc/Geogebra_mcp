# GeoGebra MCP Agent Guide

This repository supports natural-language setup by AI coding agents.

When the user asks for any of the following:

- "Set up GeoGebra MCP"
- "Install GeoGebra MCP"
- "Configure this project for Claude Code/Codex"
- "按照项目说明自动安装 GeoGebra MCP"

follow this workflow:

1. Read `skills/geogebra-setup/SKILL.md`.
2. Run the setup script from the repository root:

   ```bash
   python scripts/setup_geogebra_mcp.py
   ```

3. If dependency installation is blocked by permissions or network restrictions, ask the user to approve the command and rerun it.
4. After setup, ask the user to restart their agent session.
5. In the new session, verify with:

   ```text
   Use GeoGebra MCP to check status and draw a triangle.
   ```

For drawing and troubleshooting after installation, use:

- `skills/use-geogebra-mcp/SKILL.md` for MCP usage and diagnostics.
- `skills/geogebra-master/SKILL.md` for expert GeoGebra construction strategy.
