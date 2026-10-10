"""Pytest configuration for the Cyfolds tests."""

import sys

import pytest

# This directory holds a Cython experiment run from inside Vim, not pytest tests.
collect_ignore = ["test_cython_simple"]


@pytest.fixture(autouse=True)
def restore_default_fold_keywords():
    """Restore the default fold keywords after each test, since the keywords are
    global state in the fold modules."""
    yield
    for name in ("pyfolds", "cyfolds"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "setup_regex_pattern"):
            module.setup_regex_pattern()
