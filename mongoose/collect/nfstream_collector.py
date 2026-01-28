import datetime
from threading import Thread

from nfstream import NFStreamer

from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import NFStreamConfiguration
from mongoose.models.network_dpi import NetworkDPI
from mongoose.utils.protocols import PROTOCOL_NUMBERS


class NFStreamCollector(Thread):
    """
    Collector that reads network flows using NFStreamer in a separate thread.

    This class extends `threading.Thread` to run flow collection concurrently.
    It instantiates an `NFStreamer` using values from `NFStreamConfiguration`,
    converts each captured NFStreamer flow into the project's `NetworkFlow`
    model, resolves a human-readable protocol name via `PROTOCOL_NUMBERS`,
    and publishes the flow to a `ProcessingQueue`.

    Attributes:
        configuration: Configuration object providing `interface` and
            `active_timeout` used to configure `NFStreamer`.
        processing_queue: Queue used to publish `NetworkFlow` objects for
            downstream processing.
        disabled: Flag used to disable collection early (checked in `collect`).
    """

    def __init__(self, configuration: NFStreamConfiguration):
        """
        Initialize the collector with the provided configuration.

        Args:
            configuration: An `NFStreamConfiguration` instance containing
                `interface` and `active_timeout` values.

        The initialization creates a dedicated `ProcessingQueue` and sets
        `disabled` to False so collection can start when `start()` is called
        on the thread.
        """
        super().__init__()
        self.configuration = configuration
        self.processing_queue = ProcessingQueue()
        self.disabled = False
        self.topic = ProcessingTopic.NETWORK_DPI

    @staticmethod
    def resolve_protocol(flow: NetworkDPI):
        """
        Resolve and set the protocol keyword on a `NetworkFlow` based on
        the numeric protocol value.

        Args:
            flow: `NetworkFlow` instance with a `protocol_number` attribute.

        Behavior:
            - Looks up `protocol_number` in `PROTOCOL_NUMBERS`.
            - If found, sets `flow.protocol` to the mapping's `"keyword"`.
            - If not found, leaves `flow.protocol` unchanged (may be None).
        """
        protocol_number = flow.protocol_number
        protocol_details = PROTOCOL_NUMBERS.get(protocol_number, None)
        if protocol_details:
            flow.protocol = protocol_details.get("keyword")

    def run(self):
        """
        Thread entrypoint.

        Calls `collect()` so this object can be started via `thread.start()`.
        """
        self.collect()

    def collect(self):
        """
        Perform flow collection using NFStreamer.

        This method:
            - Checks the `disabled` flag and returns immediately if set.
            - Creates an `NFStreamer` configured with `interface` and
              `active_timeout` from `configuration`.
            - Iterates flows emitted by `NFStreamer`, converts them to
              `NetworkFlow` objects (excluding the `id` field), resolves
              the protocol keyword, and publishes each flow to
              `processing_queue` under `ProcessingTopic.NETWORK_FLOW` topic.
            - Stops if `processing_queue.processing_stopped()` returns True.

        Edge cases and behavior notes:
            - If `disabled` is set while iteration is ongoing, the method
              will not interrupt the current NFStreamer iterator directly;
              setting `disabled` prevents starting a new collection and can
              be used to guard re-entry.
        """
        if self.disabled:
            return
        streamer = NFStreamer(
            source=self.configuration.interface,
            active_timeout=self.configuration.active_timeout,
            max_nflows=self.configuration.max_nflows
        )
        for _flow in streamer:
            # Build NetworkFlow from NFStreamer flow attributes, excluding 'id'
            flow = NetworkDPI(**{
                k: getattr(_flow, k)
                for k in _flow.keys()
                if k != "id"
            })
            # Convert times
            flow.time = datetime.datetime.fromtimestamp(_flow.bidirectional_first_seen_ms / 1000.0).astimezone()
            flow.timestamp = flow.time.timestamp()
            # Resolve human-readable protocol name if available
            self.resolve_protocol(flow)
            # Publish the processed flow for downstream handling
            self.processing_queue.publish(self.topic, flow)

            # Allow an external stop request via the processing queue
            if self.processing_queue.processing_stopped():
                break

    def disable(self):
        """
        Disable the collector to prevent further collection.

        Sets the `disabled` flag so subsequent calls to `collect()` will
        return immediately. Does not forcibly terminate an ongoing
        iteration over an active `NFStreamer`.
        """
        self.disabled = True
