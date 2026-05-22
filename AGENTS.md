# GeoGebra MCP Agent Guide

This repository supports natural-language setup by AI coding agents.

When the user asks for any of the following:

- "Set up GeoGebra MCP"
- "Install GeoGebra MCP"
- "Configure this project for Claude Code/Codex"
- "按照项目说明自动安装 GeoGebra MCP"

follow this workflow:

1. Read `skills/geogebra-setup/SKILL.md`.
2. Ask the user which AI agent(s) to configure (Claude Code, Codex, or both) before running the setup script. Wait for their response.
3. Run the setup script from the repository root with the appropriate `--agent` flag:

   ```bash
   python scripts/setup_geogebra_mcp.py --agent <choice>
   ```

   Where `<choice>` is `claude`, `codex`, or `all` based on the user's answer.

4. If dependency installation is blocked by permissions or network restrictions, ask the user to approve the command and rerun it.
5. After setup, ask the user to restart their agent session.
6. In the new session, verify with:

   ```text
   Use GeoGebra MCP to check status and draw a triangle.
   ```

For drawing and troubleshooting after installation, use:

- `skills/use-geogebra-mcp/SKILL.md` for MCP usage and diagnostics.
- `skills/geogebra-master/SKILL.md` for expert GeoGebra construction strategy.

## Skill Development Guidelines

When modifying skill files, follow these checks before committing to prevent test-set pollution:

1. **Eliminate construction-type-specific residue.** Search skill files for content that overfits to one type of drawing task — e.g., hardcoded mechanism parameters (such as crank-rocker's `O1=(0,0)`, `O2=(6,0)`, link lengths 5 and 4), specific slider speeds, or workflows that only apply to one construction type. Example patterns in skills (such as mechanism templates) should serve as references, not the only path. Ensure the skill works equally well for function graphs, plane geometry, 3D graphics, data charts, and mechanism animations.

2. **Verify with a different construction type.** After modifying a skill, test it with at least one drawing task of a different type than the one used for debugging. For example, if you tuned the skill using four-bar linkage tasks, also test a function graph or 3D graphics task to confirm the modification did not break other construction workflows.

3. **Commit only skill-related files.** Run `git status` and verify the staging area contains only `skills/` files, project docs, or config files. Test-generated `.ggb` files, exported `.png` screenshots, and debug construction commands must not be committed.
