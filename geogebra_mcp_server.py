"""Backward-compatible entry point for geogebra_mcp.server."""

from geogebra_mcp.server import *  # noqa: F401,F403
from geogebra_mcp.server import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
