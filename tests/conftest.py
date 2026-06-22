"""pytest configuration for ws_core tests."""

import os
import sys

# Allow importing custom_components.ws_core without a full HA environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Disable pytest-socket entirely on Windows because it breaks ProactorEventLoop
import pytest_socket

pytest_socket.disable_socket = lambda *args, **kwargs: None
pytest_socket.SocketBlockedError = Exception


def pytest_sessionstart(session):
    pytest_socket.enable_socket()
