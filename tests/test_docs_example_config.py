"""Test that the example config in docs/example_config_test.yaml validates
against the application's Pydantic Configuration model.

This helps CI detect regressions in docs vs the actual model.
"""

from pathlib import Path


def test_docs_example_config_valid(docs_example_config) -> None:
    """Ensure the fixture returns a validated Configuration instance.

    The fixture is defined in ``tests/conftest.py`` and performs YAML
    loading and Pydantic validation; this test only performs basic
    sanity checks on the object returned by the fixture.
    """
    config = docs_example_config

    # Sanity checks to ensure the parsed model contains expected top-level keys
    assert hasattr(config, "collector")
    assert hasattr(config, "forwarder")
    assert config.database_path is not None
