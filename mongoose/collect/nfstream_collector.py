# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import logging
from threading import Thread

from nfstream import NFStreamer

from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import NFStreamConfiguration
from mongoose.models.network_dpi import NetworkDPI
from mongoose.utils.protocols import PROTOCOL_NUMBERS

logger = logging.getLogger(__name__)


class NFStreamCollector(Thread):
    """
    Collector that reads network flows using NFStreamer in a
    separate thread.

    This class extends `threading.Thread` to run flow collection
    concurrently. It instantiates an `NFStreamer` using values from
    `NFStreamConfiguration`, converts each captured NFStreamer flow
    into the project's `NetworkDPI` model, resolves a human-readable
    protocol name via `PROTOCOL_NUMBERS`, and publishes the flow to
    a `ProcessingQueue`.

    The collector attempts to be robust: it logs exceptions,
    performs safe conversions for protocol and timestamps, and
    closes the streamer resource (if supported) on shutdown.
    """

    def __init__(self, configuration: NFStreamConfiguration):
        """
        Initialize the collector with the provided configuration.

        Args:
            configuration: An `NFStreamConfiguration` instance
                containing `interface`, `active_timeout`.
        """
        super().__init__()
        self.daemon = True

        self.configuration = configuration
        """Configuration object providing `interface` and `active_timeout` used to configure `NFStreamer`."""

        self.processing_queue = ProcessingQueue()
        self.topic = ProcessingTopic.NETWORK_DPI

    @staticmethod
    def resolve_protocol(flow: NetworkDPI) -> None:
        """
        Resolve and set the protocol keyword on a `NetworkDPI` based on
        the numeric protocol value.

        Args:
            flow: `NetworkDPI` instance with a `protocol_number`
                attribute.

        Behavior:
            - Looks up `protocol_number` in `PROTOCOL_NUMBERS`.
            - If found, sets `flow.protocol` to the mapping's "keyword".
            - If not found or `protocol_number` is invalid, leaves `flow.protocol` unchanged (may be None).
        """
        protocol_number = getattr(flow, "protocol_number", None)
        try:
            # ignore None or negative sentinel values
            if protocol_number is None:
                return
            if isinstance(protocol_number, int) and protocol_number < 0:
                return
            # ensure it's an int (some streamers might expose as str)
            protocol_key = int(protocol_number)
        except (TypeError, ValueError):
            return

        protocol_details = PROTOCOL_NUMBERS.get(protocol_key)
        if protocol_details:
            flow.protocol = protocol_details.get("keyword")

    def run(self):
        """
        Thread entrypoint: delegate to `collect()` so this object
        can be started via `thread.start()`.
        """
        self.collect()

    def collect(self) -> None:
        """
        Perform flow collection using NFStreamer.

        This method:
            - Creates an `NFStreamer` configured with `interface`,
              `active_timeout`.
            - Iterates flows emitted by `NFStreamer`, converts them
              to `NetworkDPI` objects (excluding the `id` field),
              resolves the protocol keyword, and publishes each flow
              to `processing_queue` under `ProcessingTopic.NETWORK_DPI`.
            - Stops if `processing_queue.processing_stopped()` returns
              True.
        """
        try:
            streamer = NFStreamer(
                source=self.configuration.interface,
                active_timeout=self.configuration.active_timeout,
                idle_timeout=30,
            )
        except (Exception,):
            logger.exception("Failed to create NFStreamer, stopping here")
            return

        try:
            for _flow in streamer:
                # Allow an external stop request via the processing queue
                if self.processing_queue.processing_stopped():
                    logger.info("Processing queue signaled stop; stopping collector loop")
                    # raise
                    return

                try:
                    flow = NetworkDPI(**{k: getattr(_flow, k) for k in _flow.keys() if k != "id"})
                except (Exception,):
                    logger.exception("Failed to construct NetworkDPI from flow; skipping this flow")
                    continue

                try:
                    proto_val = getattr(_flow, "protocol", None)
                    flow.protocol_number = int(proto_val) if proto_val is not None else -1
                except (TypeError, ValueError):
                    flow.protocol_number = -1

                ms = getattr(_flow, "bidirectional_first_seen_ms", None)
                try:
                    ts = float(ms) / 1000.0
                    flow.time = datetime.datetime.fromtimestamp(ts).astimezone()
                    flow.timestamp = flow.time.timestamp()
                except (Exception,):
                    logger.debug("Invalid or missing timestamp on flow; using epoch fallback")
                    flow.time = datetime.datetime.fromtimestamp(0).astimezone()
                    flow.timestamp = 0.0

                # Resolve the human-readable protocol name if available
                try:
                    self.resolve_protocol(flow)
                except (Exception,):
                    logger.exception("Protocol resolution failed for flow")

                # Publish the processed flow for downstream handling
                try:
                    self.processing_queue.publish(self.topic, flow)
                except (Exception,):
                    logger.exception("Failed to publish flow to processing queue")
        except (Exception,):
            logger.exception("Unexpected error while iterating NFStreamer")
