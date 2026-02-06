import time

from mongoose.core.cache import SeverityCache, reset_singletons


def test_singleton_configuration_first_wins():
    reset_singletons()
    # Create SeverityCache with specific configuration
    s1 = SeverityCache(max_size=3, ttl_seconds=1)
    # Attempt to create again with different params
    s2 = SeverityCache(max_size=10, ttl_seconds=10)
    assert s1 is s2
    # The configuration should be the one from the first construction
    assert s1.max_size == 3
    assert s1._ttl_seconds == 1.0


def test_ttl_expiry_behavior():
    reset_singletons()
    s = SeverityCache(max_size=10, ttl_seconds=0.2)
    s.clear()
    s.set_severity("cid1", 5)
    assert s.get_severity("cid1") == 5
    time.sleep(0.25)
    assert s.get_severity("cid1") is None


def test_lru_eviction():
    reset_singletons()
    s = SeverityCache(max_size=3, ttl_seconds=None)
    s.clear()
    # Insert 3 items
    s.set_severity("a", 1)
    s.set_severity("b", 2)
    s.set_severity("c", 3)
    # Access 'a' to make it MRU
    assert s.get_severity("a") == 1
    # Insert 'd' which should evict LRU (which is 'b')
    s.set_severity("d", 4)
    assert s.get_severity("b") is None
    # 'a', 'c', 'd' should be present
    assert s.get_severity("a") == 1
    assert s.get_severity("c") == 3
    assert s.get_severity("d") == 4
