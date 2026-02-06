"""Command-line entrypoint for the Mongoose engine.

Provides a simple CLI that starts the Engine, supports systemd-style
notifications (when available), and handles graceful shutdown and reload
(signals: SIGINT/SIGTERM -> stop, SIGHUP -> reload).
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path
from typing import Optional

try:
    # systemd's python library exposes notify() which we can call
    # when running under systemd to report readiness and stopping.
    from systemd.daemon import notify  # type: ignore
except Exception:

    def notify(message: str) -> None:  # type: ignore
        """Fallback notify no-op when systemd libraries are unavailable."""
        # No-op when systemd notification isn't available.
        return


from mongoose.core.engine import Engine


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
        default=str(Path(__file__).resolve().parents[2] / "configuration_example.yaml"),
    )
    parser.add_argument(
        "-l",
        "--logging-level",
        dest="logging_level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        default="INFO",
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
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
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
    log = logging.getLogger("mongoose.cmd")

    config_path = Path(args.config)
    if not config_path.exists():
        log.warning("Configuration file %s does not exist; attempting to continue", config_path)

    try:
        engine = Engine(str(config_path))
    except Exception as e:
        log.exception("Failed to initialize Engine: %s", e)
        return 2

    stop_event = threading.Event()

    def _handle_stop(signum: int, frame) -> None:  # pragma: no cover - signal handlers
        """Handle termination signals by stopping the engine and setting the stop event."""
        log.info("Received signal %s, stopping...", signum)
        try:
            notify("STOPPING=1")
        except Exception:
            # Best effort; ignore notify failures
            pass
        try:
            engine.stop()
        except Exception:
            log.exception("Exception while stopping engine")
        finally:
            stop_event.set()

    def _handle_reload(signum: int, frame) -> None:  # pragma: no cover - signal handlers
        """Handle SIGHUP by reloading configuration and restarting components."""
        log.info("Received SIGHUP (%s): reloading configuration...", signum)
        try:
            engine.reload()
        except Exception:
            log.exception("Exception while reloading engine configuration")

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    # SIGHUP is commonly used to signal a reload on POSIX systems
    signal.signal(signal.SIGHUP, _handle_reload)

    # Start the engine and notify systemd (if available)
    try:
        engine.start()
        try:
            notify("READY=1")
        except Exception:
            pass
        log.info("Mongoose engine started (config=%s)", config_path)

        # Block until stop_event is set by a signal handler
        stop_event.wait()

        # Exiting: ensure engine is stopped (if not already)
        try:
            engine.stop()
        except Exception:
            log.exception("Exception while stopping engine during shutdown")

        try:
            notify("STOPPING=1")
        except Exception:
            pass

        log.info("Mongoose engine shutdown complete")
        return 0
    except Exception:
        log.exception("Unhandled exception in main loop")
        try:
            notify("STOPPING=1")
        except Exception:
            pass
        return 3


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
