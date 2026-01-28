import json
import logging
import socket
from threading import Thread

from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import SuricataEveConfiguration
from mongoose.models.network_alert import NetworkAlert
from mongoose.models.network_flow import NetworkFlow

logger = logging.getLogger(__name__)


class SuricataEveCollector(Thread):
    """
    Collector that reads Suricata EVE JSON events from a Unix socket in a separate thread.

    This class extends `threading.Thread` to run event collection concurrently.
    It connects to a Suricata Unix socket, parses each EVE JSON line, and converts
    'alert' and 'netflow' events into `NetworkAlert` and `NetworkFlow` models
    respectively, then publishes them to a `ProcessingQueue`.

    It handles socket connection retries and ensures graceful termination through
    the `ProcessingQueue` stop signal or the `disabled` flag.

    Attributes:
        configuration: Configuration object providing `socket_path`.
        processing_queue: Queue used to publish events for downstream processing.
        disabled: Flag used to disable collection early.
    """

    def __init__(self, configuration: SuricataEveConfiguration):
        """
        Initialize the collector with the provided configuration.

        Args:
            configuration: A `SuricataEveConfiguration` instance containing `socket_path`.
        """
        super().__init__()
        self.configuration = configuration
        self.processing_queue = ProcessingQueue()
        self.disabled = False

    def run(self):
        """
        Thread entrypoint.

        Calls `collect()` so this object can be started via `thread.start()`.
        """
        self.collect()

    def collect(self):
        """
        Perform event collection from Suricata Unix socket.

        This method:
            - Connects to the Unix socket specified in `configuration`.
            - Reads the stream and splits it into JSON objects (one per line).
            - Dispatches 'alert' and 'netflow' events to their respective topics.
            - Stops if `processing_queue.processing_stopped()` or `disabled` is True.
        """
        if self.disabled:
            return

        while not self.processing_queue.processing_stopped():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(self.configuration.socket_path)
                    logger.info(f"Connected to Suricata socket at {self.configuration.socket_path}")

                    # Suricata EVE socket is a stream of JSON objects, each followed by a newline.
                    # We can use a file-like object to read line by line.
                    with client.makefile('r') as socket_file:
                        for line in socket_file:
                            if not line.strip():
                                continue
                            try:
                                event = json.loads(line)
                                self._process_event(event)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to decode EVE JSON: {line}")
                            except Exception as e:
                                logger.error(f"Error processing Suricata event: {e}")

            except (socket.error, FileNotFoundError) as e:
                logger.error(f"Socket error: {e}. Retrying in 5 seconds...")
                # Use a wait that can be interrupted by the stop signals
                for _ in range(50):
                    if self.processing_queue.processing_stopped():
                        break
                    import time
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Unexpected error in Suricata collector: {e}")
                break

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

        if event_type == "alert":
            # Map EVE alert to NetworkAlert
            alert_data = event.copy()
            # Extract alert sub-dictionary if present, as NetworkAlert fields 
            # might be partially in 'alert' key and partially at top level
            if "alert" in event:
                alert_data.update(event["alert"])

            # Map common fields if they differ
            if "proto" in event:
                alert_data["protocol"] = event["proto"]
            if "dest_ip" in event:
                alert_data["dst_ip"] = event["dest_ip"]
            if "dest_port" in event:
                alert_data["dst_port"] = event["dest_port"]

            alert = NetworkAlert(**alert_data)
            self.processing_queue.publish(ProcessingTopic.NETWORK_ALERT, alert)

        elif event_type == "netflow":
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

    def disable(self):
        """
        Disable the collector.

        Sets the `disabled` flag to True, which will cause `collect()` to stop
        processing further events from the socket.
        """
        self.disabled = True
