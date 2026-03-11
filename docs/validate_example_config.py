# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validate the example YAML against the application's Pydantic model.

This script loads ``docs/example_config_test.yaml`` and attempts to parse it
into ``mongoose.models.configuration.Configuration``. On success it prints
"Validation succeeded" and the parsed model as JSON. On failure it prints
validation errors.
"""

import sys
from pathlib import Path
import yaml

try:
    from mongoose.models.configuration import Configuration
except Exception as exc:
    print("ERROR: could not import the configuration model:", exc)
    sys.exit(2)

CONFIG_PATH = Path(__file__).with_name("example_config_test.yaml")


def main() -> int:
    """Load YAML and validate against the Configuration model.

    Returns 0 on success, non-zero on validation or IO error.
    """
    if not CONFIG_PATH.exists():
        print(f"ERROR: config file not found: {CONFIG_PATH}")
        return 3

    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text())
    except Exception as exc:
        print("ERROR: failed to load YAML:", exc)
        return 4

    try:
        cfg = Configuration(**raw)
    except Exception as exc:
        print("VALIDATION FAILED:\n", exc)
        return 5

    print("Validation succeeded")
    # Print the parsed Configuration as a dict for manual inspection
    print(cfg.json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
