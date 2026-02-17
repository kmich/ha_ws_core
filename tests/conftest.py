"""pytest configuration for ws_core tests."""

import os
import sys

# Allow importing custom_components.ws_core without a full HA environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
