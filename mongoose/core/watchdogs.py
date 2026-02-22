import logging
from pathlib import Path
from typing import Type, Callable, List

import yaml
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class DropInConfigurationWatcher:
    def __init__(self, configuration_dir: Path, event_handler: FileSystemEventHandler):
        self.configuration_dir = configuration_dir
        self.event_handler = event_handler
        self.observer = Observer()

    def run(self):
        logger.info(f"Starting drop-in configuration watcher on {self.configuration_dir}")
        self.observer.schedule(self.event_handler, str(self.configuration_dir), recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()


class DropInConfigurationHandler(FileSystemEventHandler):
    def __init__(self, config_class: Type, callback: Callable):
        self.config_class = config_class
        self.callback = callback
        super().__init__()

    def _load_configuration(self, config_file: Path):
        with config_file.open(mode="r") as f:
            config_data = yaml.safe_load(f)
        if config_data:
            config_data["configuration_file"] = config_file
            return self.config_class(**config_data)
        return None

    def on_any_event(self, event: FileSystemEvent):
        created: List[Type[self.config_class]] = []
        modified: List[Type[self.config_class]] = []
        deleted: List[Path] = []

        src_file = Path(event.src_path)
        logging.info(f"{src_file} {event.event_type}")

        if event.is_directory:
            return
        elif event.event_type == "created":
            new_configuration = self._load_configuration(src_file)
            if new_configuration:
                created.append(new_configuration)
        elif event.event_type == "modified":
            new_configuration = self._load_configuration(src_file)
            if new_configuration:
                modified.append(new_configuration)
        elif event.event_type == "deleted":
            deleted.append(src_file)

        if self.callback:
            self.callback(created=created, modified=modified, deleted=deleted)
