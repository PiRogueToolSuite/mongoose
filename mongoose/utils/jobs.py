import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyFileDownloadJob:
    def __init__(self, url, local_path, run_time="09:00"):
        """
        Initialize a daily file download job.

        Args:
            url: URL to download the file from
            local_path: Local path to save the file
            run_time: Time to run daily download in "HH:MM" format (24-hour)
        """
        self.url = url
        self.local_path: Path = Path(local_path)
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_time = self._parse_run_time(run_time)
        self.stop_event = threading.Event()
        self.thread = None

    def _parse_run_time(self, run_time_str):
        """Parse run time string to hours and minutes."""
        try:
            hour, minute = map(int, run_time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time range")
            return hour, minute
        except (ValueError, AttributeError):
            logger.error(f"Invalid run_time format: {run_time_str}. Must be in 'HH:MM' format")
            raise ValueError("run_time must be in 'HH:MM' format")

    def _get_next_run_time(self):
        """Calculate the next run time based on the current time."""
        now = datetime.now()
        run_hour, run_minute = self.run_time
        next_run = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)

        # If today's run time has passed, schedule for tomorrow
        if next_run <= now:
            next_run += timedelta(days=1)

        return next_run

    def _file_needs_update(self):
        """Check if the file needs to be downloaded (doesn't exist or is older than a day)."""
        try:
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(self.local_path))
            one_day_ago = datetime.now() - timedelta(days=1)
            needs_update = file_mod_time < one_day_ago
            if needs_update:
                logger.info(f"File {self.local_path} is older than 24 hours, needs update")
            else:
                logger.debug(f"File {self.local_path} is up to date")
            return needs_update
        except OSError as e:
            logger.warning(f"Could not get file modification time for {self.local_path}: {e}")
            # If we can't get file info, assume it needs to be updated
            return True

    def _download_file(self):
        """Download the file from URL to the local path."""
        try:
            logger.info(f"Starting download from {self.url} to {self.local_path}")
            urllib.request.urlretrieve(self.url, self.local_path)
            logger.info(f"Download completed successfully to {self.local_path}")
            return True
        except urllib.error.URLError as e:
            logger.error(f"Network error during download from {self.url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during download from {self.url}: {e}")
            return False

    def _run_immediate_download_if_needed(self):
        """Check and perform immediate download if the file needs update."""
        if self._file_needs_update():
            logger.info("Performing immediate download due to outdated or missing file")
            return self._download_file()
        return True

    def _run_loop(self):
        """Main execution loop."""
        logger.info("Daily file download job started")

        # First, check if the immediate download is needed
        self._run_immediate_download_if_needed()

        while not self.stop_event.is_set():
            next_run = self._get_next_run_time()
            sleep_time = (next_run - datetime.now()).total_seconds()

            logger.info(f"Next scheduled download: {next_run}")

            # Wait until the next run time or the stop event
            if self.stop_event.wait(timeout=sleep_time):
                logger.info("Stop event received, exiting download loop")
                break

            # Execute daily download if not stopping
            if not self.stop_event.is_set():
                self._download_file()

    def start(self):
        """Start the daily download job in a background thread."""
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Download job is already running")
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=False)
        self.thread.start()
        logger.info(f"Daily file download job started for {self.url}")

    def stop(self, timeout=30):
        """
        Stop the download job gracefully.

        Args:
            timeout: Maximum time to wait for graceful shutdown (seconds)
        """
        if self.thread is None or not self.thread.is_alive():
            logger.debug("Download job is not running")
            return True

        logger.info("Stopping daily download job...")
        self.stop_event.set()

        # Wait for the thread to finish gracefully
        self.thread.join(timeout=timeout)

        if self.thread.is_alive():
            logger.warning("Download job did not stop gracefully within timeout")
            return False
        else:
            logger.info("Daily download job stopped successfully")
            return True
