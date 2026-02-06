import json
import socket
import threading
import time
from pathlib import Path

import pytest

from mongoose.collect.suricata_eve_collector import SuricataEveCollector
from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.models.configuration import SuricataEveConfiguration


@pytest.skip("Socket hanging when run with pytest Oo", allow_module_level=True)
def test_suricata_eve_collector_real_data():
    socket_path = Path("/tmp/suricata_test.socket")
    # 1. Prepare configuration
    config = SuricataEveConfiguration(socket_path=socket_path, collect_alerts=True, collect_netflow=True)

    # 2. Initialize collector
    collector = SuricataEveCollector(config)

    # Subscribe to topics to avoid TopicNotFoundException
    alert_q = collector.processing_queue.subscribe(ProcessingTopic.NETWORK_ALERT, "test_alert")
    flow_q = collector.processing_queue.subscribe(ProcessingTopic.NETWORK_FLOW, "test_flow")

    # 3. Create a mock Suricata socket server (DGRAM)
    def mock_suricata_sender():
        # Wait until the collector has bound the socket
        retries = 20
        while not socket_path.exists() and retries > 0:
            time.sleep(0.1)
            retries -= 1

        # if not socket_path.exists():
        #     return

        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
            with open(Path("tests/data/suricata_eve.json"), "r") as f:
                content = f.read()
                # Simple parser for the concatenated JSON
                decoder = json.JSONDecoder()
                pos = 0
                while pos < len(content):
                    content = content.lstrip()
                    if not content:
                        break
                    try:
                        obj, index = decoder.raw_decode(content)
                        line = json.dumps(obj) + "\n"
                        try:
                            server.sendto(line.encode(), str(socket_path))
                        except socket.error as e:
                            print(f"Send error: {e}")
                        content = content[index:].lstrip()
                        time.sleep(0.01)  # Small delay
                    except json.JSONDecodeError:
                        break

    sender_thread = threading.Thread(target=mock_suricata_sender)

    # 4. Start collector
    collector.start()
    sender_thread.start()

    # 5. Collect results with timeout
    start_time = time.time()
    alerts = []
    flows = []

    timeout = 30
    while time.time() - start_time < timeout:
        try:
            while not alert_q.empty():
                alerts.append(alert_q.get_nowait())
                alert_q.task_done()
            while not flow_q.empty():
                flows.append(flow_q.get_nowait())
                flow_q.task_done()
        except (Exception,):
            pass

        # There is 1 alert and 34 netflows in the sample file
        if len(alerts) >= 1 and len(flows) >= 34:
            break
        time.sleep(0.1)

    # 6. Stop collector
    ProcessingQueue().stop_processing()
    ProcessingQueue().queues.clear()
    ProcessingQueue().join()

    collector.join(timeout=0.2)
    sender_thread.join(timeout=0.2)

    # 7. Assertions
    assert len(alerts) > 0, f"Should have collected at least one alert, got {len(alerts)}"
    assert len(flows) > 0, f"Should have collected netflows, got {len(flows)}"

    # Verify alert details from the last entry in suricata_eve.json
    alert = alerts[0]
    assert alert.signature == "SURICATA DNS"
    assert alert.src_ip == "192.168.0.12"
    assert alert.dst_ip == "8.8.8.8"

    # Verify some flow
    flow = flows[0]
    assert flow.src_ip == "192.168.2.1"
    assert flow.dst_ip == "255.255.255.255"
