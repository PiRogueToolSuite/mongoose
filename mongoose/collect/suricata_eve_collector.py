import json
import logging
import socket
from threading import Thread

from mongoose.core.cache import SeverityCache
from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import SuricataEveConfiguration
from mongoose.models.network_alert import NetworkAlert
from mongoose.models.network_flow import NetworkFlow

logger = logging.getLogger(__name__)


class SuricataEveCollector(Thread):  # pragma: no cover
    """
    Collector that reads Suricata EVE JSON events from a Unix socket in a separate thread.

    This class extends `threading.Thread` to run event collection concurrently.
    It connects to a Suricata Unix socket, parses each EVE JSON line, and converts
    'alert' and 'netflow' events into `NetworkAlert` and `NetworkFlow` models
    respectively, then publishes them to a `ProcessingQueue`.

    It handles socket connection retries and ensures graceful termination through
    the `ProcessingQueue` stop signal or the `disabled` flag.
    """

    def __init__(self, configuration: SuricataEveConfiguration):
        """
        Initialize the collector with the provided configuration.

        Args:
            configuration: A `SuricataEveConfiguration` instance containing `socket_path`.
        """
        super().__init__()
        self.daemon = True
        self.severy_cache = SeverityCache()

        self.configuration = configuration
        """Configuration object providing `socket_path`."""

        self.processing_queue = ProcessingQueue()
        """Queue used to publish events for downstream processing."""

    def run(self):
        """
        Thread entrypoint.

        Calls `collect()` so this object can be started via `thread.start()`.
        """
        self.collect()

    def read_socket_with_timeout(self, timeout=5.0):
        # Create the socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        # Bind to the path
        if self.configuration.socket_path.exists():
            self.configuration.socket_path.unlink(missing_ok=True)
        sock.bind(str(self.configuration.socket_path))

        sock.settimeout(timeout)

        try:
            while not self.processing_queue.processing_stopped():
                try:
                    # 65535 is the max size for a UDP/Unix dgram packet
                    data, addr = sock.recvfrom(65535)

                    # Decode and split by newline in case multiple events
                    # were bundled in a single datagram
                    decoded_data = data.decode("utf-8").strip()
                    for line in decoded_data.split("\n"):
                        if line:
                            yield line  # Send the line back to the main loop

                except socket.timeout:
                    logger.info(f"[!] No data received within {timeout}. Still waiting...")
                    continue
        except (socket.error, socket.timeout, FileNotFoundError) as e:
            logger.error(f"Socket error: {e}")

    def collect(self):
        """
        Perform event collection from Suricata Unix socket.

        This method:
            - Connects to the Unix socket specified in `configuration`.
            - Reads the stream and splits it into JSON objects (one per line).
            - Dispatches 'alert' and 'netflow' events to their respective topics.
            - Stops if `processing_queue.processing_stopped()`.
        """
        if self.configuration.socket_path.exists():
            self.configuration.socket_path.unlink()

        for line in self.read_socket_with_timeout(5.0):
            if self.processing_queue.processing_stopped():
                break

            if not line.strip():
                continue
            try:
                event = json.loads(line)
                self._process_event(event)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode EVE JSON: {line}")
            except Exception as e:
                logger.error(f"Error processing Suricata event: {e}")

        logger.info("Suricata EVE collector stopped")

    def _process_event(self, event: dict):
        """
        Process a single EVE event and publish it if it's an alert or netflow.

        This method maps raw Suricata EVE JSON fields to `NetworkAlert` or `NetworkFlow`
        models. It handles field normalization (e.g., mapping `dest_ip` to `dst_ip`)
        and merging sub-dictionaries (e.g., merging the `alert` or `netflow` key
        into the top-level data).

        Args:
            event: A dictionary representing a single Suricata EVE JSON event.
        """
        event_type = event.get("event_type")
        if event_type == "alert" and self.configuration.collect_alerts:
            # Map EVE alert to NetworkAlert
            alert_data = event.copy()
            # Extract alert sub-dictionary if present, as NetworkAlert fields
            # might be partially in 'alert' key and partially at top level
            if "alert" in event:
                alert_data.update(event["alert"])

            app_proto = event.get("app_proto")
            if app_proto in event:
                alert_data["extra"] = event[app_proto]

            # Map common fields if they differ
            if "proto" in event:
                alert_data["protocol"] = event["proto"]
            if "dest_ip" in event:
                alert_data["dst_ip"] = event["dest_ip"]
            if "dest_port" in event:
                alert_data["dst_port"] = event["dest_port"]

            alert = NetworkAlert(**alert_data)
            # Cache the alert severity
            if alert.severity == 1:
                self.severy_cache.set_severity(alert.community_id, 2)  # highest risk
            else:
                self.severy_cache.set_severity(alert.community_id, 1)  # mid-level of risk

            self.processing_queue.publish(ProcessingTopic.NETWORK_ALERT, alert)

        elif event_type == "netflow" and self.configuration.collect_netflow:
            # Map EVE netflow to NetworkFlow
            flow_data = event.copy()
            if "netflow" in event:
                # Merge netflow sub-dictionary and map fields
                netflow = event["netflow"]
                flow_data.update(netflow)
                if "pkts" in netflow:
                    flow_data["packets"] = netflow["pkts"]

            # Map common fields
            if "proto" in event:
                flow_data["protocol"] = event["proto"]
            if "dest_ip" in event:
                flow_data["dst_ip"] = event["dest_ip"]
            if "dest_port" in event:
                flow_data["dst_port"] = event["dest_port"]

            flow = NetworkFlow(**flow_data)
            self.processing_queue.publish(ProcessingTopic.NETWORK_FLOW, flow)
