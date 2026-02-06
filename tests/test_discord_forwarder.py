import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from mongoose.forward.discord import DiscordForwarder, DiscordFormatter
from mongoose.models.configuration import DiscordForwarderConfiguration
from mongoose.models import NetworkAlert


class DiscordReceiverMock:
    """Mocks Discord by patching requests.Session.post."""

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

    def add_response(self, status_code=204, exception=None):
        """Queue a response or exception to be returned by the next POST request."""
        self.responses.append((status_code, exception))

    def _handle_post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})

        if not self.responses:
            mock_resp = MagicMock(spec=requests.Response)
            mock_resp.status_code = 204
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
def discord_receiver():
    receiver = DiscordReceiverMock()
    receiver.start()
    yield receiver
    receiver.stop()


def make_alert() -> NetworkAlert:
    return NetworkAlert(
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


def test_discord_formatter_alert():
    alert = make_alert()
    formatted = DiscordFormatter.format(alert)
    assert "embeds" in formatted
    # Check JSON serializable
    json.dumps(formatted)


def test_discord_forwarder_basic_alert(discord_receiver):
    config = DiscordForwarderConfiguration(url="https://discord.com/api/webhooks/test", topics=["network-alert"])
    forwarder = DiscordForwarder(config)

    alert = make_alert()

    discord_receiver.add_response(status_code=204)

    forwarder.forward(alert)

    assert len(discord_receiver.requests) == 1
    req = discord_receiver.requests[0]
    assert req["url"] == "https://discord.com/api/webhooks/test"
    assert "json" in req


def test_discord_forwarder_retries_on_5xx(discord_receiver):
    # 5xx should be retried
    config = DiscordForwarderConfiguration(url="https://discord.com/api/webhooks/test", retry_count=1, retry_delay=0.01)
    forwarder = DiscordForwarder(config)

    alert = make_alert()

    # First response 500, then 204
    discord_receiver.add_response(status_code=500)
    discord_receiver.add_response(status_code=204)

    forwarder.forward(alert)
    assert len(discord_receiver.requests) == 2


def test_discord_forwarder_no_retry_on_4xx(discord_receiver):
    # 4xx should not be retried and should raise
    config = DiscordForwarderConfiguration(url="https://discord.com/api/webhooks/test", retry_count=2, retry_delay=0.01)
    forwarder = DiscordForwarder(config)

    alert = make_alert()

    discord_receiver.add_response(status_code=400)

    with pytest.raises(requests.exceptions.HTTPError):
        forwarder.forward(alert)


def test_allowed_mentions_applied(discord_receiver):
    # Ensure allowed_mentions from config are included in payload
    config = DiscordForwarderConfiguration(
        url="https://discord.com/api/webhooks/test", allowed_mentions={"parse": ["users"]}
    )
    forwarder = DiscordForwarder(config)

    alert = make_alert()

    discord_receiver.add_response(status_code=204)

    forwarder.forward(alert)
    assert len(discord_receiver.requests) == 1
    req = discord_receiver.requests[0]
    assert req["json"]["allowed_mentions"]["parse"] == ["users"]
