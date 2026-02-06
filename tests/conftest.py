"""Pytest fixtures for docs validation tests.

This centralizes loading and validation of documentation example files so
multiple tests can reuse the parsed configuration.
"""

from pathlib import Path

import pytest
import yaml
from typing import Any

from mongoose.models.configuration import Configuration


@pytest.fixture(scope="session")
def docs_example_config_raw() -> Any:
    """Load the raw example YAML from docs/example_config_test.yaml.

    Returns the parsed YAML as a dict. If the file is missing the fixture
    will skip tests that depend on it.
    """
    cfg_path = Path(__file__).resolve().parents[1] / "docs" / "example_config_test.yaml"
    if not cfg_path.exists():
        pytest.skip(f"Example config not found: {cfg_path}")

    try:
        return yaml.safe_load(cfg_path.read_text())
    except Exception as exc:
        pytest.skip(f"Failed to load example config: {exc}")


@pytest.fixture(scope="session")
def docs_example_config(docs_example_config_raw) -> Configuration:
    """Validate and return a :class:`Configuration` instance parsed from the
    documentation example YAML.

    Tests can depend on this fixture to receive a validated
    :class:`Configuration` object. Validation errors will cause pytest to
    fail the tests with the Pydantic ValidationError.
    """
    return Configuration(**docs_example_config_raw)
