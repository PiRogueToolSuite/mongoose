import pytest

from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.utils.exceptions import TopicNotFoundException


def test_unsubscribe():
    pq = ProcessingQueue()
    subscriber_id = "test_subscriber"
    topic = ProcessingTopic.NETWORK_DPI

    # Reset singleton-like behavior if any (though it looks like a normal class with class attributes)
    # Actually, subscribers and queues are class attributes, which is a bit strange if multiple instances are intended.
    # Let's check if they are indeed class attributes.
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()

    # Subscribe
    pq.subscribe(topic, subscriber_id)
    assert subscriber_id in pq.subscribers
    assert topic in pq.queues
    assert len(pq.queues[topic]) == 1

    # Unsubscribe (method not yet implemented)
    if hasattr(pq, 'unsubscribe'):
        pq.unsubscribe(subscriber_id)
        assert subscriber_id not in pq.subscribers
        assert topic not in pq.queues or len(pq.queues[topic]) == 0

        # Verify that publishing to the topic now raises TopicNotFoundException if no other subscribers
        with pytest.raises(TopicNotFoundException):
            pq.publish(topic, "test data")
    else:
        pytest.fail("ProcessingQueue has no unsubscribe method")


def test_unsubscribe_not_found():
    pq = ProcessingQueue()
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()

    # Should not raise any exception
    pq.unsubscribe("non_existent_subscriber")


def test_unsubscribe_partial_others_remain():
    pq = ProcessingQueue()
    sub1 = "sub1"
    sub2 = "sub2"
    topic = ProcessingTopic.NETWORK_DPI

    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()

    pq.subscribe(topic, sub1)
    pq.subscribe(topic, sub2)

    assert len(pq.queues[topic]) == 2

    pq.unsubscribe(sub1)

    assert sub1 not in pq.subscribers
    assert sub2 in pq.subscribers
    assert topic in pq.queues
    assert len(pq.queues[topic]) == 1

    # Can still publish to sub2
    pq.publish(topic, "data")
    q2 = pq.subscribers[sub2][topic]
    assert q2.get_nowait() == "data"
