import json
import os
import re
import socket
import threading
import time

import pytest

from mongoose.collect.suricata_eve_collector import SuricataEveCollector
from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import SuricataEveConfiguration


@pytest.fixture(autouse=True)
def reset_processing_queue():
    """Reset the singleton-like attributes of ProcessingQueue before each test."""
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()
    ProcessingQueue.stop_processing_event.clear()


class MockSuricataSocket:
    def __init__(self, socket_path, data_file):
        self.socket_path = socket_path
        self.data_file = data_file
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists(socket_path):
            os.remove(socket_path)
        self.server_socket.bind(socket_path)
        self.server_socket.listen(1)
        self.running = True
        self.thread = threading.Thread(target=self.run)

    def start(self):
        self.thread.start()

    def run(self):
        try:
            self.server_socket.settimeout(1.0)
            while self.running:
                try:
                    conn, _ = self.server_socket.accept()
                    with conn:
                        with open(self.data_file, "r") as f:
                            content = f.read()
                            # Split multi-line JSON objects
                            json_objs = re.findall(r"\{.*?^\}", content, re.DOTALL | re.MULTILINE)
                            for obj in json_objs:
                                try:
                                    # Validate and compact
                                    data = json.loads(obj)
                                    single_line = json.dumps(data)
                                    conn.sendall(single_line.encode() + b"\n")
                                except json.JSONDecodeError:
                                    continue
                                time.sleep(0.01)
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            self.server_socket.close()

    def stop(self):
        self.running = False
        self.thread.join()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)


def test_suricata_eve_collector_real_data():
    socket_path = "/tmp/suricata_test.socket"
    data_file = "tests/data/suricata_eve.json"

    mock_server = MockSuricataSocket(socket_path, data_file)
    mock_server.start()

    config = SuricataEveConfiguration(socket_path=socket_path)
    collector = SuricataEveCollector(config)

    pq = ProcessingQueue()
    flow_q = pq.subscribe(ProcessingTopic.NETWORK_FLOW, "test_sub")
    alert_q = pq.subscribe(ProcessingTopic.NETWORK_ALERT, "test_sub_alerts")

    collector.start()

    received_alerts = []
    start_time = time.time()
    # Expect 1 alert from the file
    while len(received_alerts) < 1 and (time.time() - start_time) < 10:
        if not alert_q.empty():
            received_alerts.append(alert_q.get_nowait())
        else:
            time.sleep(0.1)

    received_flows = []
    start_time = time.time()
    # Expect 34 flows from the file
    while len(received_flows) < 34 and (time.time() - start_time) < 10:
        if not flow_q.empty():
            received_flows.append(flow_q.get_nowait())
        else:
            time.sleep(0.1)

    collector.disable()
    pq.stop_processing()
    collector.join(timeout=2)
    mock_server.stop()

    assert len(received_flows) == 34
    for flow in received_flows:
        assert flow.src_ip is not None
        assert flow.dst_ip is not None
        assert flow.protocol is not None
        assert flow.packets > 0


def test_suricata_eve_collector_alert_mapping():
    # Since we don't have an alert in the json file, we test mapping logic here
    # with a sample alert JSON that matches Suricata EVE format
    alert_event = {
        "timestamp": "2026-01-27T21:00:00.000000+0100",
        "flow_id": 12345,
        "event_type": "alert",
        "src_ip": "1.2.3.4",
        "src_port": 123,
        "dest_ip": "5.6.7.8",
        "dest_port": 456,
        "proto": "TCP",
        "alert": {
            "action": "allowed",
            "gid": 1,
            "signature_id": 2000001,
            "rev": 1,
            "signature": "ET POLICY Test Alert",
            "category": "Potentially Bad Traffic",
            "severity": 2,
        },
    }

    pq = ProcessingQueue()
    alert_q = pq.subscribe(ProcessingTopic.NETWORK_ALERT, "alert_sub")

    config = SuricataEveConfiguration(socket_path="/tmp/dummy")
    collector = SuricataEveCollector(config)

    collector._process_event(alert_event)

    assert not alert_q.empty()
    alert = alert_q.get_nowait()

    assert alert.src_ip == "1.2.3.4"
    assert alert.dst_ip == "5.6.7.8"
    assert alert.protocol == "TCP"
    assert alert.signature == "ET POLICY Test Alert"
    assert alert.severity == 2
    assert alert.action == "allowed"
