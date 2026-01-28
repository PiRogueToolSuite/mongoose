import os
import time

import pytest

from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.store.sqlite import SqliteStore
from mongoose.models import NetworkAlert, NetworkAlertTable, NetworkFlow, NetworkFlowTable, NetworkDPI, NetworkDPITable


@pytest.fixture
def db_path():
    path = "test_mongoose.db"
    if os.path.exists(path):
        os.remove(path)
    yield path
    # if os.path.exists(path):
    #     os.remove(path)


@pytest.fixture(autouse=True)
def reset_processing_queue():
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()
    ProcessingQueue.stop_processing_event.clear()


def test_sqlite_store_save_alert(db_path):
    pq = ProcessingQueue()
    store = SqliteStore(db_path=db_path)
    store.start()

    alert = NetworkAlert(
        flow_id=1,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        community_id="test",
        action="allowed",
        gid=1,
        signature_id=1,
        rev=1,
        signature="test signature",
        category="test category",
        severity=1,
    )

    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)

    # Wait for the worker thread to process
    max_retries = 10
    found = False
    for _ in range(max_retries):
        with store.Session() as session:
            count = session.query(NetworkAlertTable).count()
            if count > 0:
                found = True
                break
        time.sleep(0.1)

    assert found
    with store.Session() as session:
        record = session.query(NetworkAlertTable).first()
        assert record.src_ip == "1.1.1.1"
        assert record.dst_ip == "2.2.2.2"
        assert record.community_id_b64 != ""

    pq.stop_processing()


def test_sqlite_store_save_all_types(db_path):
    pq = ProcessingQueue()
    store = SqliteStore(db_path=db_path)
    store.start()

    alert = NetworkAlert(
        flow_id=1,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        action="allowed",
        gid=1,
        signature_id=1,
        rev=1,
        signature="s",
        category="c",
        severity=1,
    )
    flow = NetworkFlow(
        flow_id=2,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        packets=10,
        bytes=1000,
        start="2023-01-01T00:00:00",
        end="2023-01-01T00:00:01",
        age=1,
    )
    dpi = NetworkDPI(
        ip_version=4,
        src_ip="1.1.1.1",
        src_port=123,
        src_mac="aa:bb:cc",
        dst_ip="2.2.2.2",
        dst_port=80,
        dst_mac="dd:ee:ff",
        dst2src_bytes=500,
        src2dst_bytes=500,
    )

    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    pq.publish(ProcessingTopic.NETWORK_FLOW, flow)
    pq.publish(ProcessingTopic.NETWORK_DPI, dpi)

    # Wait for the worker thread to process
    max_retries = 20
    for _ in range(max_retries):
        with store.Session() as session:
            if (
                session.query(NetworkAlertTable).count() > 0
                and session.query(NetworkFlowTable).count() > 0
                and session.query(NetworkDPITable).count() > 0
            ):
                break
        time.sleep(0.1)

    with store.Session() as session:
        assert session.query(NetworkAlertTable).count() == 1
        assert session.query(NetworkFlowTable).count() == 1
        assert session.query(NetworkDPITable).count() == 1

    pq.stop_processing()
