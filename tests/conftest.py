"""pytest fixtures and configuration for GeoGebra MCP tests."""

import os
import sys
import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def clean_env():
    """Remove GEOGEBRA_CDP_PORT from environment for predictable defaults."""
    old = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    yield
    if old is not None:
        os.environ["GEOGEBRA_CDP_PORT"] = old
    else:
        os.environ.pop("GEOGEBRA_CDP_PORT", None)
