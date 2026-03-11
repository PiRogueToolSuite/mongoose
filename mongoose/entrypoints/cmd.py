# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command-line entrypoint for the Mongoose engine.

Provides a simple CLI that starts the Engine, supports systemd-style
notifications (when available), and handles graceful shutdown (SIGINT/SIGTERM -> stop).
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Optional
from mongoose.core.engine import Engine


# Systemd
try:
    from systemd.daemon import notify  # type: ignore
except (Exception,):

    def notify(message: str) -> None:  # type: ignore
        return


# PiRogue
pirogue_isolated_iface: Optional[str] = None
try:
    from pirogue_admin_client import PirogueAdminClientAdapter

    admin_client = PirogueAdminClientAdapter()
    pirogue_isolated_iface = admin_client.get_configuration().get("ISOLATED_INTERFACE")
except (Exception,):
    pass


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional list of arguments (used for testing). If None, uses
              sys.argv.

    Returns:
        argparse.Namespace with attributes `config` and `logging_level`.
    """
    parser = argparse.ArgumentParser(description="Mongoose engine CLI")
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        help="Path to configuration YAML file",
        default="/etc/mongoose/mongoose.yaml",
    )
    parser.add_argument(
        "-l",
        "--logging-level",
        dest="logging_level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        default="INFO",
    )
    parser.add_argument(
        "-i",
        "--interface",
        dest="interface",
        help="Network interface to be used by NFStream if enabled",
        default="",
    )
    return parser.parse_args(argv)


def _configure_logging(level_name: str) -> None:
    """Configure the root logger.

    Accepts common level names (case-insensitive) and falls back to INFO for
    invalid input.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [%(thread)d] %(name)s: %(message)s",
    )


def main(argv: Optional[list[str]] = None) -> int:
    """Main entrypoint used by the console script.

    This function sets up signal handlers and blocks until a termination
    signal is received. SIGHUP triggers a configuration reload.

    Returns:
        Exit code (0 for clean shutdown, non-zero on error).
    """
    args = parse_args(argv)
    _configure_logging(args.logging_level)
    log = logging.getLogger(f"mongoose {threading.get_ident()}")
    config_path = Path(args.config)

    if not config_path.exists():
        log.warning("Configuration file %s does not exist; attempting to continue", config_path)
        return 1

    network_interface = args.interface or pirogue_isolated_iface or None

    try:
        engine = Engine(str(config_path), args.interface)
    except Exception as e:
        log.exception("Failed to initialize Engine: %s", e)
        return 2

    def _handle_stop(signum: int, frame) -> None:  # pragma: no cover - signal handlers
        """Handle termination signals by stopping the engine and setting the stop event."""
        log.info("Received signal %s, stopping...", signum)
        if threading.get_ident() != engine.thread_id:
            log.debug("Received signal from other thread")
            log.debug(f"Engine thread: {engine.thread_id} != Current thread: {threading.get_ident()}")
        if engine.started:
            engine.stop()
        try:
            notify("STOPPING=1")
        except (Exception,):
            pass
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    # Start the engine and notify systemd (if available)
    try:
        engine.start()
        try:
            notify("READY=1")
        except (Exception,):
            pass
        log.info("Mongoose engine started (config=%s)", config_path)
        signal.pause()
        return 0
    except (Exception,):
        log.exception("Unhandled exception in main loop")
        try:
            notify("STOPPING=1")
        except (Exception,):
            return 3
    return 0


def main_cli():
    sys.exit(main())


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main_cli()
