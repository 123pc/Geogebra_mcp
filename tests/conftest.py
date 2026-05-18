"""pytest fixtures and configuration for GeoGebra MCP tests."""

import os
import sys
import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def clean_env():
    """Remove GEOGEBRA_* env vars for predictable test defaults."""
    old_cdp = os.environ.pop("GEOGEBRA_CDP_PORT", None)
    old_restart = os.environ.pop("GEOGEBRA_RESTART_EXISTING", None)
    yield
    if old_cdp is not None:
        os.environ["GEOGEBRA_CDP_PORT"] = old_cdp
    else:
        os.environ.pop("GEOGEBRA_CDP_PORT", None)
    if old_restart is not None:
        os.environ["GEOGEBRA_RESTART_EXISTING"] = old_restart
    else:
        os.environ.pop("GEOGEBRA_RESTART_EXISTING", None)
