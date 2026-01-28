import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import SecretStr

from mongoose.core.engine import ProcessingQueue, ProcessingTopic
from mongoose.forward.webhook import WebhookForwarder, WebhookFormatter
from mongoose.models.configuration import WebhookForwarderConfiguration
from mongoose.models import NetworkAlert


class WebhookReceiverMock:
    """Mocks a remote webhook receiver by patching requests.Session.post."""

    def __init__(self):
        self.requests = []
        self.responses = []
        self._patcher = None
        self._mock_post = None

    def start(self):
        self._patcher = patch.object(requests.Session, "post")
        self._mock_post = self._patcher.start()
        self._mock_post.side_effect = self._handle_post

    def stop(self):
        if self._patcher:
            self._patcher.stop()

    def add_response(self, status_code=200, exception=None):
        """Queue a response or exception to be returned by the next POST request."""
        self.responses.append((status_code, exception))

    def _handle_post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})

        if not self.responses:
            # Default response
            mock_resp = MagicMock(spec=requests.Response)
            mock_resp.status_code = 200
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        status_code, exception = self.responses.pop(0)
        if exception:
            raise exception

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = status_code
        if 400 <= status_code < 600:
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                f"{status_code} Error", response=mock_resp
            )
        else:
            mock_resp.raise_for_status.return_value = None
        return mock_resp


@pytest.fixture
def webhook_receiver():
    receiver = WebhookReceiverMock()
    receiver.start()
    yield receiver
    receiver.stop()


@pytest.fixture(autouse=True)
def reset_processing_queue():
    ProcessingQueue.subscribers.clear()
    ProcessingQueue.queues.clear()
    ProcessingQueue.stop_processing_event.clear()


def test_webhook_formatter_alert():
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
    formatted = WebhookFormatter.format(alert)
    assert formatted["src_ip"] == "1.1.1.1"
    assert formatted["dst_ip"] == "2.2.2.2"
    assert "time" in formatted
    # Check if it's JSON serializable
    json.dumps(formatted)


def test_webhook_forwarder_basic_flow(webhook_receiver):
    config = WebhookForwarderConfiguration(url="http://example.com/webhook", retry_count=0, topics=["network-alert"])

    pq = ProcessingQueue()
    forwarder = WebhookForwarder(config)

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

    webhook_receiver.add_response(status_code=200)

    forwarder.start()
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)

    # Give it a moment to process
    time.sleep(0.5)

    assert len(webhook_receiver.requests) == 1
    req = webhook_receiver.requests[0]
    assert req["url"] == "http://example.com/webhook"
    assert req["json"]["src_ip"] == "1.1.1.1"

    pq.stop_processing()


def test_webhook_forwarder_auth_bearer():
    config = WebhookForwarderConfiguration(
        url="http://example.com/webhook", auth_type="bearer", auth_token=SecretStr("mytoken"), topics=["network-alert"]
    )

    forwarder = WebhookForwarder(config)
    assert forwarder._session.headers["Authorization"] == "Bearer mytoken"


def test_webhook_forwarder_auth_header():
    config = WebhookForwarderConfiguration(
        url="http://example.com/webhook",
        auth_type="header",
        auth_token=SecretStr("my-api-key"),
        auth_header_name="X-Custom-Key",
        topics=["network-alert"],
    )

    forwarder = WebhookForwarder(config)
    assert forwarder._session.headers["X-Custom-Key"] == "my-api-key"


def test_webhook_forwarder_retries(webhook_receiver):
    config = WebhookForwarderConfiguration(
        url="http://example.com/webhook", retry_count=1, retry_delay=0.1, topics=["network-alert"]
    )

    pq = ProcessingQueue()
    forwarder = WebhookForwarder(config)

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

    # First call fails with ConnectionError, second succeeds
    webhook_receiver.add_response(exception=requests.exceptions.ConnectionError("Failed"))
    webhook_receiver.add_response(status_code=200)

    forwarder.start()
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)

    time.sleep(0.5)

    assert len(webhook_receiver.requests) == 2

    pq.stop_processing()


def test_webhook_configuration_validation():
    with pytest.raises(ValueError, match="auth_type must be one of"):
        WebhookForwarderConfiguration(url="http://example.com", auth_type="invalid")

    with pytest.raises(ValueError, match="auth_token is required"):
        WebhookForwarderConfiguration(url="http://example.com", auth_type="bearer")

    with pytest.raises(ValueError, match="must be in 'user:pass' format"):
        WebhookForwarderConfiguration(url="http://example.com", auth_type="basic", auth_token=SecretStr("not-a-pair"))


def test_webhook_forwarder_bulk_mode(webhook_receiver):
    config = WebhookForwarderConfiguration(
        url="http://example.com/webhook", mode="bulk", bulk_size=2, topics=["network-alert"]
    )

    pq = ProcessingQueue()
    forwarder = WebhookForwarder(config)

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

    forwarder.start()

    # Publish 1st alert - should not trigger send yet
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    time.sleep(0.2)
    assert len(webhook_receiver.requests) == 0

    # Publish 2nd alert - should trigger send
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    time.sleep(0.5)

    assert len(webhook_receiver.requests) == 1
    assert isinstance(webhook_receiver.requests[0]["json"], list)
    assert len(webhook_receiver.requests[0]["json"]) == 2

    pq.stop_processing()


def test_webhook_forwarder_periodic_mode(webhook_receiver):
    config = WebhookForwarderConfiguration(
        url="http://example.com/webhook",
        mode="periodic",
        periodic_interval=0.5,
        periodic_rate=2,
        topics=["network-alert"],
    )

    pq = ProcessingQueue()
    forwarder = WebhookForwarder(config)

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

    forwarder.start()

    # Publish 3 alerts
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)
    pq.publish(ProcessingTopic.NETWORK_ALERT, alert)

    # Should not have sent anything immediately
    assert len(webhook_receiver.requests) == 0

    # Wait for interval
    time.sleep(0.7)

    # Should have sent 2 alerts (periodic_rate)
    assert len(webhook_receiver.requests) == 1
    assert len(webhook_receiver.requests[0]["json"]) == 2

    # Wait for another interval
    time.sleep(0.6)

    # Should have sent the remaining 1 alert
    assert len(webhook_receiver.requests) == 2
    assert len(webhook_receiver.requests[1]["json"]) == 1

    pq.stop_processing()
