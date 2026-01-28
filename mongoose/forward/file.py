import json
import logging
import os
from typing import Any

from mongoose.core.engine import ProcessingTopic
from mongoose.forward.base import BaseForwarder, BaseFormatter
from mongoose.models.configuration import FileForwarderConfiguration

logger = logging.getLogger(__name__)


class FileFormatter(BaseFormatter):
    """Formats network data for file storage.

    This class handles the conversion of network models (DPI, Alert, Flow) into
    JSON-serializable strings. It ensures that complex types like datetime
    objects are correctly converted to strings and that any Pydantic-specific
    fields are handled according to the Pydantic version in use.
    """

    @staticmethod
    def format(data: Any) -> str:
        """Format the given data into a JSON string.

        Args:
            data: The model instance or data object to format.

        Returns:
            A JSON string representation of the data followed by a newline.
            Returns an empty string if formatting fails.
        """
        try:
            payload = BaseFormatter.to_dict(data)

            # Ensure complex types are handled
            return json.dumps(payload, default=str)
        except Exception as e:
            logger.error(f"Failed to format data for file forwarder: {e}")
            return ""


class FileForwarder(BaseForwarder):
    """Forwards network events to files asynchronously.

    Subscribes to specified topics and appends data to a file for each topic.
    Files are stored in the configured output directory. It manages its own
    background worker thread for non-blocking operation.

    Security considerations:
        - **Permissions**: Ensure the output directory has appropriate permissions
          to prevent unauthorized access to the dumped network data.
        - **Disk space**: Monitor disk space as files will grow indefinitely
          since this forwarder appends data without rotation or cleanup.
        - **Sensitive data**: Network event data may contain sensitive infrastructure
          information (IPs, ports, protocol details). Ensure the storage medium
          is secured.
    """

    def __init__(self, config: FileForwarderConfiguration):
        """Initialize the FileForwarder.

        Args:
            config: A FileForwarderConfiguration instance.
        """
        super().__init__(topics=config.topics)
        self.config = config
        self.formatter = FileFormatter()
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Ensure the output directory exists."""
        if not os.path.exists(self.config.output_dir):
            os.makedirs(self.config.output_dir, exist_ok=True)
            logger.info(f"Created output directory: {self.config.output_dir}")

    def forward(self, data: Any):
        """Write formatted data to the appropriate topic file.

        Args:
            data: The data to write (Pydantic model instance).
        """
        # Determine the topic of the data
        topic = self._get_topic_for_data(data)
        if not topic:
            return

        formatted_data = self.formatter.format(data)
        if not formatted_data:
            return

        filename = f"{self.config.prefix}{topic.value}.json"
        filepath = os.path.join(self.config.output_dir, filename)

        try:
            with open(filepath, "a") as f:
                f.write(formatted_data + "\n")
        except Exception as e:
            logger.error(f"Failed to write data to {filepath}: {e}")

    def _get_topic_for_data(self, data: Any) -> ProcessingTopic | None:
        """Determine the topic for the given data instance."""
        from mongoose.models import NetworkAlert, NetworkFlow, NetworkDPI
        
        if isinstance(data, NetworkAlert):
            return ProcessingTopic.NETWORK_ALERT
        if isinstance(data, NetworkFlow):
            return ProcessingTopic.NETWORK_FLOW
        if isinstance(data, NetworkDPI):
            return ProcessingTopic.NETWORK_DPI
        
        return None
