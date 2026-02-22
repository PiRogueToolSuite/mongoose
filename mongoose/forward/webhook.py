import logging
import time
from typing import Any, Dict

import requests
from requests.auth import HTTPBasicAuth

from mongoose.forward.base import BaseForwarder, BaseFormatter
from mongoose.models.configuration import WebhookForwarderConfiguration

logger = logging.getLogger(__name__)


class WebhookFormatter(BaseFormatter):
    """Formats network data for webhook consumption.

    This class handles the conversion of network models (DPI, Alert, Flow) into
    JSON-serializable dictionaries. It ensures that complex types like datetime
    objects are correctly converted to strings and that any Pydantic-specific
    fields are handled according to the Pydantic version in use.

    Security considerations:
        - The formatter performs a JSON round-trip to ensure data consistency
          and safety before it is sent over the network.
        - It uses a custom default for serialization to prevent failures on
          complex types, ensuring robust operation even with unexpected data.
    """

    @staticmethod
    def format(data: Any) -> Dict[str, Any]:
        """Format the given data into a dictionary for JSON serialization.

        Handles Pydantic v1/v2 instances and generic objects.

        Args:
            data: The model instance or data object to format.

        Returns:
            A dictionary representation of the data, guaranteed to be JSON serializable.
            Returns an error dictionary if formatting fails.
        """
        try:
            payload = BaseFormatter.to_dict(data)

            # Ensure it's JSON serializable by doing a round-trip with a custom default
            import json

            return json.loads(json.dumps(payload, default=str))
        except Exception as e:
            logger.error(f"Failed to format data for webhook: {e}")
            return {"error": "formatting_failed", "details": str(e)}


class WebhookForwarder(BaseForwarder):
    """Forwards network events to a remote webhook asynchronously.

    Subscribes to specified topics and sends data to a configured URL using HTTP POST.
    It manages its own background worker thread for non-blocking operation and
    supports various authentication methods and retry logic.

    Notes:
        - **Authentication**: Supports Basic Auth, Bearer tokens, and custom headers.
          Credentials should be provided via `WebhookConfiguration` using `SecretStr`
          to prevent accidental leakage in logs.
        - **SSL/TLS**: SSL certificate verification is enabled by default (`verify_ssl=True`).
          It is highly recommended to keep this enabled in production.
        - **Sensitive data**: While Mongoose normalizes data, users should ensure the
          webhook endpoint is secured (HTTPS) as network event data may contain
          sensitive infrastructure information (IPs, ports, protocol details).
        - **Isolation**: Each forwarder uses a dedicated `requests.Session` for
          connection pooling and to keep authentication headers isolated.
        - **Forwarding modes**:
            - `immediate`: Sends data as soon as it is received.
            - `bulk`: Accumulates data up to `bulk_size` or until a timeout occurs.
            - `periodic`: Sends data at a fixed `periodic_interval` at a maximum `periodic_rate`.
    """

    def __init__(self, config: WebhookForwarderConfiguration):
        """Initialize the WebhookForwarder.

        Args:
            config: A WebhookConfiguration instance defining the destination and security settings.
        """
        super().__init__(topics=config.topics)
        self.config = config
        self.formatter = WebhookFormatter()
        self._session = self._setup_session()
        self._buffer = []

    def _setup_session(self) -> requests.Session:
        """Set up a requests Session with authentication and security settings.

        Configures the session with custom headers, User-Agent, and applies
        SSL verification and authentication based on the configuration.

        Returns:
            A configured requests.Session object.
        """
        session = requests.Session()
        session.verify = self.config.verify_ssl
        session.headers.update({"User-Agent": "Mongoose-Webhook-Forwarder/1.0", "Content-Type": "application/json"})
        session.headers.update(self.config.headers)
        self._apply_authentication(session)
        return session

    def _apply_authentication(self, session: requests.Session):
        """Apply configured authentication to the session.

        Based on `config.auth_type`, this method sets up HTTP Basic Auth,
        Bearer Token in the Authorization header, or a custom API key header.

        Args:
            session: The requests.Session to configure.
        """
        if not self.config.auth_token:
            return

        token = self.config.auth_token.get_secret_value()

        if self.config.auth_type == "basic":
            username, password = token.split(":", 1)
            session.auth = HTTPBasicAuth(username, password)
        elif self.config.auth_type == "bearer":
            session.headers["Authorization"] = f"Bearer {token}"
        elif self.config.auth_type == "header":
            session.headers[self.config.auth_header_name] = token

    def start(self):
        """Start the forwarder worker thread.

        Launches a background daemon thread that subscribes to the configured
        topics and processes incoming events.
        """
        super().start()
        logger.info(f"Forwarding to {self.config.url} [mode={self.config.mode}]")

    def _run(self):
        """Main worker loop to process messages and forward them.

        Overrides BaseForwarder._run to support different forwarding modes.
        """
        last_periodic_send = time.time()

        while not self.processing_queue.processing_stopped() and self.config.enable:
            try:
                if self.config.mode == "immediate":
                    data = self.queue.get(timeout=1.0)
                    if data is not None:
                        self.forward(data)
                        self.queue.task_done()
                elif self.config.mode == "bulk":
                    try:
                        data = self.queue.get(timeout=1.0)
                        if data is not None:
                            self._buffer.append(data)
                            if len(self._buffer) >= self.config.bulk_size:
                                self._flush_buffer()
                            self.queue.task_done()
                    except (Exception,):  # timeout
                        if self._buffer:
                            self._flush_buffer()
                elif self.config.mode == "periodic":
                    now = time.time()
                    # Collect data from queue
                    try:
                        while len(self._buffer) < self.config.periodic_rate * 2:  # Limit buffer growth
                            data = self.queue.get_nowait()
                            if data is not None:
                                self._buffer.append(data)
                                self.queue.task_done()
                    except (Exception,):  # empty queue
                        pass

                    if now - last_periodic_send >= self.config.periodic_interval:
                        if self._buffer:
                            # Send up to periodic_rate items
                            to_send = self._buffer[: self.config.periodic_rate]
                            self._buffer = self._buffer[self.config.periodic_rate :]
                            self._forward_batch(to_send)
                        last_periodic_send = now

                    time.sleep(0.1)  # Avoid tight loop

            except Exception as e:
                import queue as q

                if isinstance(e, q.Empty):
                    continue
                logger.error(f"Error in {self.__class__.__name__} worker: {e}")

        # Final flush
        if self._buffer:
            self._flush_buffer()

    def _flush_buffer(self):
        """Send all data in the buffer."""
        if not self._buffer:
            return
        self._forward_batch(self._buffer)
        self._buffer = []

    def _forward_batch(self, batch: list):
        """Format and send a batch of data.

        Args:
            batch: List of data objects to forward.
        """
        payloads = []
        for data in batch:
            payload = self.formatter.format(data)
            if payload.get("error") != "formatting_failed":
                payloads.append(payload)

        if not payloads:
            return

        # If it's a single item and NOT periodic/bulk, we might want to send it as is,
        # but for consistency and simplicity in bulk/periodic we send it as a list if there are multiple.
        # However, many webhooks expect a single object or a list.
        data_to_send = payloads if len(payloads) > 1 or self.config.mode != "immediate" else payloads[0]

        for attempt in range(self.config.retry_count + 1):
            try:
                self._send_payload(data_to_send)
                logger.debug(f"Successfully forwarded {len(payloads)} items to {self.config.url}")
                return
            except requests.exceptions.RequestException as e:
                if not self._should_retry(e, attempt):
                    break
                time.sleep(self.config.retry_delay)

    def disable(self):
        """Disable the forwarder."""
        self.config.enable = False
        self.processing_queue.unsubscribe(self.subscriber_id)

    def forward(self, data: Any):
        """Send formatted data to the webhook URL with retries.

        Orchestrates the formatting of data and the retry loop for delivery.

        Args:
            data: The data to forward (Pydantic model instance).
        """

        self._forward_batch([data])

    def _send_payload(self, payload: Dict[str, Any]):
        """Execute the HTTP POST request.

        Args:
            payload: The dictionary to send as JSON.

        Raises:
            requests.exceptions.RequestException: If the request fails or returns an error status.
        """
        response = self._session.post(str(self.config.url), json=payload, timeout=self.config.timeout)
        response.raise_for_status()

    def _should_retry(self, exception: requests.exceptions.RequestException, attempt: int) -> bool:
        """Determine if a request should be retried based on the exception and attempt count.

        Args:
            exception: The exception encountered during the request.
            attempt: The current attempt number (starting at 0).

        Returns:
            True if the request should be retried, False otherwise.
        """
        should_retry = True
        if response := getattr(exception, "response", None):
            if 400 <= response.status_code < 500:
                should_retry = False
                logger.error(f"Client error ({response.status_code}) when forwarding to {self.config.url}: {exception}")

        if should_retry and attempt < self.config.retry_count:
            logger.warning(
                f"Attempt {attempt + 1} failed to forward to {self.config.url}: {exception}. "
                f"Retrying in {self.config.retry_delay}s..."
            )
            return True

        if should_retry:
            logger.error(
                f"Failed to forward data to {self.config.url} after {self.config.retry_count + 1} attempts: {exception}"
            )
        return False


# Discord-specific forwarder implementation moved to `mongoose.forward.discord`.
# See mongoose/forward/discord.py for the DiscordFormatter and DiscordForwarder
