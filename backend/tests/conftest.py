"""
Pytest configuration for backend tests.
"""
import pytest


@pytest.fixture(autouse=True)
def disable_real_openrouter_by_default(monkeypatch):
    """
    Ensure automated tests never make real external calls to OpenRouter by default.
    Specific AI tests can explicitly configure a mock key and mock httpx.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
