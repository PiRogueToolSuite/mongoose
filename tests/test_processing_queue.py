# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from queue import Full

import pytest

from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.utils.exceptions import TopicNotFoundException


@pytest.fixture(autouse=True)
def reset_processing_queue():
    """Reset the singleton-like attributes of ProcessingQueue before each test."""
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()
    ProcessingQueue.stop_processing_event.clear()


def test_single_topic_subscription_and_publish():
    pq = ProcessingQueue()
    subscriber_id = "sub1"
    q = pq.subscribe(ProcessingTopic.NETWORK_DPI, subscriber_id)

    data = {"test": "data"}
    pq.publish(ProcessingTopic.NETWORK_DPI, data)

    assert q.get_nowait() == data
    assert q.empty()


def test_multi_topic_subscription_list():
    pq = ProcessingQueue()
    subscriber_id = "sub1"
    topics = [ProcessingTopic.NETWORK_DPI, ProcessingTopic.NETWORK_ALERT]
    q = pq.subscribe(topics, subscriber_id)

    data1 = {"type": "dpi"}
    data2 = {"type": "alert"}

    pq.publish(ProcessingTopic.NETWORK_DPI, data1)
    pq.publish(ProcessingTopic.NETWORK_ALERT, data2)

    assert q.get_nowait() == data1
    assert q.get_nowait() == data2
    assert q.empty()


def test_incremental_subscription_reuse_queue():
    pq = ProcessingQueue()
    subscriber_id = "sub1"

    q1 = pq.subscribe(ProcessingTopic.NETWORK_DPI, subscriber_id)
    q2 = pq.subscribe(ProcessingTopic.NETWORK_ALERT, subscriber_id)

    assert q1 is q2

    pq.publish(ProcessingTopic.NETWORK_DPI, "data1")
    pq.publish(ProcessingTopic.NETWORK_ALERT, "data2")

    assert q1.get_nowait() == "data1"
    assert q1.get_nowait() == "data2"


def test_multiple_subscribers_same_topic():
    pq = ProcessingQueue()
    q1 = pq.subscribe(ProcessingTopic.NETWORK_DPI, "sub1")
    q2 = pq.subscribe(ProcessingTopic.NETWORK_DPI, "sub2")

    data = "shared data"
    pq.publish(ProcessingTopic.NETWORK_DPI, data)

    assert q1.get_nowait() == data
    assert q2.get_nowait() == data


def test_publish_topic_not_found():
    pq = ProcessingQueue()
    with pytest.raises(TopicNotFoundException):
        pq.publish(ProcessingTopic.NETWORK_DPI, "data")


def test_queue_full_exception():
    pq = ProcessingQueue()
    # Subscribe with a very small queue size
    pq.subscribe(ProcessingTopic.NETWORK_DPI, "sub1", queue_size=1)

    pq.publish(ProcessingTopic.NETWORK_DPI, "data1")

    with pytest.raises(Full):
        pq.publish(ProcessingTopic.NETWORK_DPI, "data2")


def test_stop_processing_logic():
    pq = ProcessingQueue()
    assert not pq.processing_stopped()

    pq.stop_processing()
    assert pq.processing_stopped()


def test_join_logic():
    pq = ProcessingQueue()
    q = pq.subscribe(ProcessingTopic.NETWORK_DPI, "sub1")

    pq.publish(ProcessingTopic.NETWORK_DPI, "data")

    # In a real scenario, another thread would call task_done()
    # Here we just verify it doesn't crash and we can call task_done()
    item = q.get()
    assert item == "data"
    q.task_done()

    # join() should return immediately since task_done() was called
    pq.join()
