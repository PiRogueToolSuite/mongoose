import logging
import threading
from typing import Any, Dict, List, Optional

from mongoose.core.processing import ProcessingQueue, ProcessingTopic

logger = logging.getLogger(__name__)


class BaseFormatter:
    """Base class for formatters.

    Provides common logic for converting Pydantic models to dictionaries.
    """

    @staticmethod
    def to_dict(data: Any) -> Dict[str, Any]:
        """Convert the given data into a dictionary.

        Handles Pydantic v1/v2 instances and generic objects.

        Args:
            data: The model instance or data object to convert.

        Returns:
            A dictionary representation of the data.
        """
        if hasattr(data, "model_dump"):
            return data.model_dump()
        elif hasattr(data, "dict"):
            return data.dict()
        else:
            return {"data": str(data)}


class BaseForwarder:
    """Base class for all forwarders.

    Handles common tasks like subscribing to topics, managing a background
    worker thread, and the main processing loop.
    """

    def __init__(self, topics: List[str]):
        """Initialize the BaseForwarder.

        Args:
            topics: List of topic strings to subscribe to.
        """
        self.topics_config = topics
        self.processing_queue = ProcessingQueue()
        self.thread: Optional[threading.Thread] = None
        self.queue = None

    def start(self):
        """Start the forwarder worker thread.

        Launches a background daemon thread that subscribes to the configured
        topics and processes incoming events.
        """
        if self.thread and self.thread.is_alive():
            return

        topics = self._resolve_topics()
        if not topics:
            logger.error(f"No valid topics for {self.__class__.__name__} to subscribe to.")
            return

        # Unique subscriber ID to avoid collisions
        subscriber_id = f"{self.__class__.__name__.lower()}_{id(self)}"
        self.queue = self.processing_queue.subscribe(topics, subscriber_id=subscriber_id)

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"{self.__class__.__name__} started")

    def _run(self):
        """Main worker loop to process messages and forward them.

        Continuously polls the `ProcessingQueue` for new data from subscribed
        topics. Terminates gracefully when the system-wide stop signal is received.
        """
        while not self.processing_queue.processing_stopped():
            try:
                data = self.queue.get(timeout=1.0)
                if data is None:
                    self.queue.task_done()
                    continue

                self.forward(data)
                self.queue.task_done()
            except Exception as e:
                import queue as q

                if isinstance(e, q.Empty):
                    continue
                logger.error(f"Error in {self.__class__.__name__} worker: {e}")

    def _resolve_topics(self) -> List[ProcessingTopic]:
        """Convert topic strings from configuration to ProcessingTopic enums.

        Returns:
            A list of ProcessingTopic instances corresponding to configured topics.
        """
        topics = []
        for t_str in self.topics_config:
            try:
                topics.append(ProcessingTopic(t_str))
            except ValueError:
                # Handle cases where t_str might be the enum value itself
                found = False
                for pt in ProcessingTopic:
                    if pt.value == t_str:
                        topics.append(pt)
                        found = True
                        break
                if not found:
                    logger.warning(f"Unknown topic in {self.__class__.__name__} config: {t_str}")
        return topics

    def forward(self, data: Any):
        """Process and forward the data.

        To be implemented by subclasses.

        Args:
            data: The data to forward.
        """
        raise NotImplementedError("Subclasses must implement forward()")
