# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import types

import pytest

# Create a lightweight fake 'nfstream' module so importing the collector
# doesn't require the real external dependency at test-import time.
if "nfstream" not in sys.modules:
    fake_mod = types.ModuleType("nfstream")

    # Provide a default NFStreamer placeholder callable; tests will monkeypatch
    # collector_mod.NFStreamer to specific factories, so this default is only
    # needed to satisfy the import.
    def _default_streamer_factory(**kwargs):
        # an empty generator
        def gen():
            if False:
                yield None

        return gen()

    setattr(fake_mod, "NFStreamer", _default_streamer_factory)
    sys.modules["nfstream"] = fake_mod

from mongoose.collect import nfstream_collector as collector_mod
from mongoose.collect.nfstream_collector import NFStreamCollector
from mongoose.models.configuration import NFStreamConfiguration
from mongoose.core.processing import ProcessingTopic


class SimpleNetworkDPI:
    """Lightweight stand-in for NetworkDPI used in tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # fields the collector expects
        self.protocol_number = getattr(self, "protocol_number", None)
        self.protocol = getattr(self, "protocol", None)
        self.time = getattr(self, "time", None)
        self.timestamp = getattr(self, "timestamp", None)


def make_fake_flow(protocol=6, ms=1600000000000, extra_fields=None):
    """Create a fake NFStreamer flow-like object with attributes."""
    if extra_fields is None:
        extra_fields = {}
    attrs = {"protocol": protocol, "bidirectional_first_seen_ms": ms}
    attrs.update(extra_fields)

    class FakeFlow:
        def keys(self):
            return list(attrs.keys())

    f = FakeFlow()
    for k, v in attrs.items():
        setattr(f, k, v)
    return f


class FakeQueue:
    def __init__(self):
        self.published = []
        self._stopped = False

    def publish(self, topic, item):
        self.published.append((topic, item))

    def processing_stopped(self):
        return self._stopped

    def stop_processing(self):
        self._stopped = True


def fake_streamer_factory_single(flow):
    def factory(**kwargs):
        def gen():
            yield flow

        return gen()

    return factory


def fake_streamer_factory_many(flows, stop_after_first=False, queue_to_stop=None):
    def factory(**kwargs):
        for i, f in enumerate(flows):
            if stop_after_first and i == 1 and queue_to_stop is not None:
                # simulate external stop request between yields
                queue_to_stop.stop_processing()
            yield f

    return factory


def test_collect_happy_path(monkeypatch):
    # Replace NetworkDPI with a lightweight test double
    monkeypatch.setattr(collector_mod, "NetworkDPI", SimpleNetworkDPI)
    # Ensure the protocol mapping yields a known keyword
    monkeypatch.setitem(collector_mod.PROTOCOL_NUMBERS, 6, {"keyword": "tcp"})

    fake_flow = make_fake_flow(protocol=6, ms=1600000000000)
    factory = fake_streamer_factory_single(fake_flow)

    # Patch NFStreamer in the module to use our factory
    monkeypatch.setattr(collector_mod, "NFStreamer", factory)

    cfg = NFStreamConfiguration(interface="lo", active_timeout=60, max_nflows=1)
    coll = NFStreamCollector(cfg)
    # replace internal queue with our fake queue
    fake_q = FakeQueue()
    coll.processing_queue = fake_q

    coll.collect()

    assert len(fake_q.published) == 1
    topic, item = fake_q.published[0]
    assert topic == ProcessingTopic.NETWORK_DPI
    assert isinstance(item, SimpleNetworkDPI)
    # protocol keyword should be resolved
    assert item.protocol == "tcp"
    # timestamp should be ms/1000
    assert item.timestamp == pytest.approx(1600000000000 / 1000.0, rel=1e-6)


def test_time_conversion_edge_case(monkeypatch):
    monkeypatch.setattr(collector_mod, "NetworkDPI", SimpleNetworkDPI)
    monkeypatch.setitem(collector_mod.PROTOCOL_NUMBERS, 6, {"keyword": "tcp"})

    # Make ms invalid (None)
    fake_flow = make_fake_flow(protocol=6, ms=None)
    factory = fake_streamer_factory_single(fake_flow)
    monkeypatch.setattr(collector_mod, "NFStreamer", factory)

    cfg = NFStreamConfiguration(interface="lo", active_timeout=1, max_nflows=1)
    coll = NFStreamCollector(cfg)
    fake_q = FakeQueue()
    coll.processing_queue = fake_q

    coll.collect()

    assert len(fake_q.published) == 1
    _, item = fake_q.published[0]
    # fallback timestamp expected to be 0.0 (epoch)
    assert item.timestamp == 0.0
