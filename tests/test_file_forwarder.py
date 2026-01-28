import json
import os
import shutil
import time

import pytest

from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.forward.file import FileForwarder, FileFormatter
from mongoose.models.configuration import FileForwarderConfiguration
from mongoose.models import NetworkAlert, NetworkFlow


@pytest.fixture
def output_dir():
    path = "test_output"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    yield path
    if os.path.exists(path):
        shutil.rmtree(path)


@pytest.fixture(autouse=True)
def reset_processing_queue():
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()
    ProcessingQueue.stop_processing_event.clear()


def test_file_formatter_alert():
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
    formatted = FileFormatter.format(alert)
    data = json.loads(formatted)
    assert data["src_ip"] == "1.1.1.1"
    assert data["dst_ip"] == "2.2.2.2"
    assert "time" in data


def test_file_forwarder_basic_flow(output_dir):
    config = FileForwarderConfiguration(output_dir=output_dir, topics=["network-alert"], prefix="test-")

    pq = ProcessingQueue()
    forwarder = FileForwarder(config)
    forwarder.start()

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

    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)

    # Give it a moment to process
    max_retries = 10
    filepath = os.path.join(output_dir, "test-network-alert.json")

    found = False
    for _ in range(max_retries):
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                if f.read().strip():
                    found = True
                    break
        time.sleep(0.1)

    assert found
    with open(filepath, "r") as f:
        line = f.readline()
        data = json.loads(line)
        assert data["src_ip"] == "1.1.1.1"

    pq.stop_processing()


def test_file_forwarder_multiple_topics(output_dir):
    config = FileForwarderConfiguration(output_dir=output_dir, topics=["network-alert", "network-flow"])

    pq = ProcessingQueue()
    forwarder = FileForwarder(config)
    forwarder.start()

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
        src_ip="3.3.3.3",
        src_port=443,
        dst_ip="4.4.4.4",
        dst_port=123,
        protocol="UDP",
        packets=5,
        bytes=500,
        start="2023-01-01T00:00:00",
        end="2023-01-01T00:00:01",
        age=1,
    )

    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    pq.publish(ProcessingTopic.NETWORK_FLOW, flow)

    # Wait for both files
    alert_path = os.path.join(output_dir, "network-alert.json")
    flow_path = os.path.join(output_dir, "network-flow.json")

    max_retries = 20
    for _ in range(max_retries):
        if os.path.exists(alert_path) and os.path.exists(flow_path):
            break
        time.sleep(0.1)

    assert os.path.exists(alert_path)
    assert os.path.exists(flow_path)

    with open(alert_path, "r") as f:
        assert "1.1.1.1" in f.read()
    with open(flow_path, "r") as f:
        assert "3.3.3.3" in f.read()

    pq.stop_processing()
