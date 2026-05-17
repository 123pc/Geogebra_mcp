# Changelog

## [0.1.0] — Unreleased

### Changed
- Enriched `geogebra_exec` with comprehensive GeoGebra command reference
- Added mechanism templates to `geogebra_draw_mechanism` (crank-rocker, slider-crank, double-crank, four-bar)
- Added `geogebra_help` tool (commands, mechanisms, animation topics)

### Added
- MCP Server with 12 tools for controlling GeoGebra Classic 6
- Cross-platform auto-detection and auto-launch of GeoGebra (Windows/macOS/Linux)
- One-click install wizard (`python install_wizard.py`)
- Daemon auto-reconnect on crash
- Configurable CDP port via `GEOGEBRA_CDP_PORT` env var
- MIT LICENSE
- pytest test suite (37 Python + 12 Node.js tests)
- Dockerfile for containerized deployment
- pyproject.toml for pip install
- smithery.yaml for Smithery.ai registry
- Bilingual error messages (Chinese + English)
