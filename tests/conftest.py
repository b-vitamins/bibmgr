"""Pytest configuration and fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """Isolate environment variables for each test.

    This prevents test pollution where one test's environment
    changes affect other tests.
    """
    # Save current environment
    original_env = os.environ.copy()

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def skip_validation(monkeypatch):
    """Fixture to skip validation when needed."""
    monkeypatch.setenv("BIBMGR_SKIP_VALIDATION", "1")
    yield
    # Automatically cleaned up by monkeypatch
