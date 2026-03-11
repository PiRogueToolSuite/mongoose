# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import enum
import logging
from collections import defaultdict
from queue import Queue, Full
from threading import Event
from typing import Any, Dict, List

from mongoose.utils.exceptions import TopicNotFoundException

logger = logging.getLogger(__name__)


class ProcessingTopic(enum.Enum):
    NETWORK_DPI = "network-dpi"  # from NFStream if enabled
    NETWORK_ALERT = "network-alert"  # from Suricata if enabled
    NETWORK_FLOW = "network-flow"  # from Suricata if netflow is enabled
    ENRICHED_NETWORK_DPI = "enriched-network-dpi"
    ENRICHED_NETWORK_ALERT = "enriched-network-alert"
    ENRICHED_NETWORK_FLOW = "enriched-network-flow"


class ProcessingQueue:
    """A thread-safe pub-sub queue system for managing topic-based message distribution.

    This class implements a publish-subscribe pattern where:
        - Subscribers register their interest in one or more topics using `subscribe()`.
        - Publishers send data to specific topics using `publish()`.

    Internally, each subscriber receives a dedicated `queue.Queue`. When data is
    published to a topic, it is duplicated and pushed into the queues of all
    subscribers registered for that topic. This ensures that multiple subscribers
    (e.g., a database storer and a webhook forwarder) can process the same stream
    of events independently.

    Note:
        Topics are created dynamically when the first subscriber registers.
        Therefore, subscribers MUST be registered before any data is published to a topic.
        If `publish()` is called for a topic with no active subscribers, it will raise
        a `TopicNotFoundException`.
    """

    subscribers: Dict[str, Dict[ProcessingTopic, Queue]] = defaultdict(dict)
    """Mapping of subscriber IDs to their topic-specific queues."""

    queues: Dict[ProcessingTopic, List[Queue]] = defaultdict(list)
    """Mapping of topics to lists of subscriber queues."""

    stop_processing_event = Event()
    """Event flag to signal processing termination."""

    def publish(self, topic: ProcessingTopic, data: Any):
        """Publish data to all subscribers of a specific topic.

        Attempts to add data to all queues subscribed to the given topic without blocking.
        Each subscriber of the topic will receive a copy of the data in its dedicated queue.

        Args:
            topic: The topic to publish data to.
            data: The data to publish to subscribers.

        Raises:
            TopicNotFoundException: If the topic has no subscribers (no one called `subscribe()` for it).
            Full: If any subscriber's queue is full and cannot accept more data.

        Note:
            This method requires the topic to have at least one subscriber.
            If no one has subscribed to the topic yet, it is considered non-existent.
        """
        logger.debug(f"Publishing data to {topic}")
        if topic not in self.queues:
            raise TopicNotFoundException(f"Topic {topic} not found")
        for q in self.queues.get(topic, []):
            try:
                q.put_nowait(data)
            except Full as e:
                logger.error(f"Failed to publish data to {topic}: {e}")
                raise e

    def subscribe(self, topic: ProcessingTopic | List[ProcessingTopic], subscriber_id: str, queue_size=100) -> Queue:
        """Subscribe to one or more topics and receive a dedicated queue for receiving data.

        This method registers a subscriber for the specified topics. If it's the first
        time a topic is subscribed to, the topic is effectively "created" in the system.

        **Ordering requirement**: Subscribers must register before publishers attempt
        to send data to a topic.

        Creates a new queue for the subscriber if they haven't already subscribed to the topic(s).
        If multiple topics are provided, they will share the same queue for this subscriber.
        If the subscriber has already subscribed to any of the topics, returns the existing queue.

        Args:
            topic: The topic name(s) to subscribe to. Can be a single ProcessingTopic or a list.
            subscriber_id: Unique identifier for the subscriber.
            queue_size: Maximum number of items the queue can hold (default: 100).

        Returns:
            The queue for receiving published data.
        """
        topics = [topic] if isinstance(topic, ProcessingTopic) else topic
        logger.info(f"{subscriber_id} subscribing to {topics}")

        # Check if already subscribed to ANY topic and reuse that queue if so
        existing_queue = None
        if self.subscribers[subscriber_id]:
            existing_queue = next(iter(self.subscribers[subscriber_id].values()))

        if existing_queue:
            for t in topics:
                if t not in self.subscribers[subscriber_id]:
                    self.subscribers[subscriber_id][t] = existing_queue
                    self.queues[t].append(existing_queue)
            return existing_queue

        q = Queue(maxsize=queue_size)
        for t in topics:
            self.subscribers[subscriber_id][t] = q
            self.queues[t].append(q)
        return q

    def unsubscribe(self, subscriber_id: str):
        """Completely unsubscribe a subscriber and remove all associated queues.

        This method removes the subscriber from all topics they were subscribed to
        and cleans up their dedicated queues. If a topic has no more subscribers
        after this operation, it is removed from the system.

        Args:
            subscriber_id: Unique identifier for the subscriber to unsubscribe.
        """
        logger.info(f"Unsubscribing {subscriber_id}")
        if subscriber_id not in self.subscribers:
            logger.warning(f"Subscriber {subscriber_id} not found")
            return

        subscribed_topics = self.subscribers.pop(subscriber_id)
        for topic, q in subscribed_topics.items():
            if topic in self.queues:
                if q in self.queues[topic]:
                    self.queues[topic].remove(q)
                if not self.queues[topic]:
                    del self.queues[topic]

    def stop_processing(self):
        """Signal all processing operations to stop.

        Sets the stop processing event flag, which can be checked by workers
        to gracefully terminate their operations.
        """
        self.stop_processing_event.set()

    def processing_stopped(self) -> bool:
        """Check if processing has been stopped.

        Returns:
            True if stop processing has been signaled, False otherwise.
        """
        return self.stop_processing_event.is_set()

    def join(self):
        """Block until all queues have processed their tasks.

        Waits for all subscriber queues across all topics to complete processing
        their current items. This is useful for ensuring clean shutdown.
        """
        for _, queues in self.queues.items():
            for q in queues:
                q.join()
