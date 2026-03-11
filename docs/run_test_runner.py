# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run the docs example config test directly (lightweight runner).

This is not a replacement for pytest in CI, but provides a direct local
check that the test function runs and passes.
"""

import importlib.util
from pathlib import Path

TEST_FILE = Path(__file__).resolve().parents[1] / "tests" / "test_docs_example_config.py"

spec = importlib.util.spec_from_file_location("test_docs_example_config", str(TEST_FILE))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore

try:
    mod.test_docs_example_config_valid()
except AssertionError as exc:
    print("TEST FAILED:", exc)
    raise SystemExit(1)
except Exception as exc:
    print("ERROR RUNNING TEST:", exc)
    raise SystemExit(2)

print("TEST PASSED")
