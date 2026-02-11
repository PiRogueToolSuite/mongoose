import logging
import threading

import yaml
from typing import List, Optional, Type, Dict

from mongoose.core.cache import SeverityCache
from mongoose.core.processing import ProcessingQueue
from mongoose.core.sink import Sink
from mongoose.forward.discord import DiscordForwarder
from mongoose.models.configuration import Configuration, WebhookForwarderConfiguration, ForwarderConfiguration
from mongoose.collect.nfstream_collector import NFStreamCollector
from mongoose.collect.suricata_eve_collector import SuricataEveCollector
from mongoose.enrich.base import Enrich
from mongoose.forward.file import FileForwarder
from mongoose.forward.webhook import WebhookForwarder
from mongoose.store.sqlite import SqliteStore
import mongoose.core.cache as cache_module

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances: Dict[type, type] = {}

    def __call__(cls, *args, **kwargs):
        """Control instance creation to ensure singleton behavior.

        Args:
            cls (type): The class being instantiated
            *args: Positional arguments for class initialization
            **kwargs: Keyword arguments for class initialization

        Returns:
            type: The singleton instance of the class

        Note:
            If an instance already exists, ``__init__`` will still be called with
            the provided arguments, but no new instance is created.
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Engine(metaclass=Singleton):
    """
    The Engine class is responsible for loading the configuration,
    initializing components (collectors, enrichers, forwarders),
    and managing their lifecycle (start, stop, reload).
    """

    def __init__(self, config_path: str, interface: str = None):
        self.config_path = config_path
        self.config: Optional[Configuration] = None
        self.processing_queue = ProcessingQueue()
        self.collectors: List = []
        self.forwarders: List = []
        self.enrichment: Optional[Enrich] = None
        self.database_storage = None
        self.sink: Sink = Sink()
        self.interface = interface
        self.load_config()
        self._setup_components()
        self.started = False
        self.thread_id = threading.get_ident()

    def load_extra_config(self, name: str, config_class: Type):
        configurations = []
        if self.config.extra_configuration_dir.is_dir():
            config_dir = self.config.extra_configuration_dir / f"{name}.d"
            if config_dir.exists():
                for config_file in config_dir.glob("*.yaml"):
                    with config_file.open(mode="r") as f:
                        config_data = yaml.safe_load(f)
                    if config_data:
                        configurations.append(config_class(**config_data))
        return configurations

    def load_config(self):
        """Load configuration from the YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)

            if config_data and "configuration" in config_data:
                self.config = Configuration(**config_data["configuration"])
            elif config_data:
                self.config = Configuration(**config_data)
            else:
                raise ValueError("Configuration file is empty")

            configurations = self.load_extra_config("webhook", WebhookForwarderConfiguration)
            if not self.config.forwarder:
                self.config.forwarder = ForwarderConfiguration()
            self.config.forwarder.webhooks.extend(configurations)

            # Initialize severity cache from configuration (if present)
            if self.config and self.config.cache and self.config.cache.severity and self.config.cache.severity.enable:
                sev_cfg = self.config.cache.severity
                # Create the singleton SeverityCache with configured size and TTL
                # Note: SeverityCache is a singleton; the first instantiation sets the configuration.
                instance = SeverityCache(max_size=sev_cfg.max_size, ttl_seconds=sev_cfg.ttl_seconds)
                # Export module-level instance for easy import elsewhere
                cache_module.severity_cache = instance

            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {e}")
            raise

    def _setup_components(self):
        """Initialize all components based on the loaded configuration."""
        self.collectors = []
        self.forwarders = []
        self.enrichment = None

        if not self.config:
            return

        logger.debug(f"Configuration loaded from {self.config_path}")
        logger.debug(self.config)

        if not self.config.database_path.parent.is_dir():
            self.config.database_path.parent.mkdir(exist_ok=True, parents=True)

        self.database_storage = SqliteStore(self.config.database_path, history_config=self.config.history)

        # Setup Collectors
        if self.config.collector.suricata and self.config.collector.suricata.enable:
            self.collectors.append(SuricataEveCollector(self.config.collector.suricata))

        if self.config.collector.nf_stream and self.config.collector.nf_stream.enable:
            if self.interface:
                self.config.collector.nf_stream.interface = self.interface
            self.collectors.append(NFStreamCollector(self.config.collector.nf_stream))

        # Setup Enrichment
        if self.config.enrichment:
            self.enrichment = Enrich(self.config.enrichment)

        # Setup Forwarders
        if self.config.forwarder.file and self.config.forwarder.file.enable:
            self.forwarders.append(FileForwarder(self.config.forwarder.file))

        if self.config.forwarder.webhooks:
            for forwarder in self.config.forwarder.webhooks:
                if forwarder.enable:
                    self.forwarders.append(WebhookForwarder(forwarder))

        if self.config.forwarder.discord:
            for forwarder in self.config.forwarder.discord:
                if forwarder.enable:
                    self.forwarders.append(DiscordForwarder(forwarder))

    def start(self):
        """Start all configured and enabled collectors, enrichers, and forwarders."""
        logger.info("Starting Engine...")

        self.started = True

        # Reset the stop event in case it was set during a previous run
        self.processing_queue.stop_processing_event.clear()

        self.sink.start()
        self.database_storage.start()

        # Start Enricher
        if self.enrichment:
            self.enrichment.start()

        # Start Forwarders
        for forwarder in self.forwarders:
            forwarder.start()

        # Start Collectors
        for collector in self.collectors:
            collector.start()

        logger.info("Engine started successfully.")

    def stop(self):
        """Stop all processing by signaling the processing queue and waiting for threads."""
        logger.info(f"Stopping Engine... [{threading.get_ident()}]")

        self.started = False

        self.processing_queue.stop_processing()

        self.sink.stop()
        self.processing_queue.queues.clear()
        self.processing_queue.join()
        logger.info("Engine stopped successfully.")

    def reload(self):
        """Reload configuration and restart all components."""
        logger.info("Reloading Engine configuration...")
        self.stop()
        self.load_config()
        self._setup_components()
        self.start()
        logger.info("Engine reloaded successfully.")
