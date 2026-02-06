import threading
import time
from typing import List

from mongoose.core.cache import SeverityCache, reset_singletons


def worker_write(cache: SeverityCache, start: int, end: int, start_event: threading.Event):
    start_event.wait()
    for i in range(start, end):
        cache.set_severity(f"k{i}", i)


def worker_read(cache: SeverityCache, keys: List[str], start_event: threading.Event):
    # Wait briefly so reads are started together if desired
    start_event.wait()
    for k in keys:
        _ = cache.get_severity(k)


def test_concurrent_readers_writers():
    reset_singletons()
    num_threads = 8
    per_thread = 250
    total_keys = num_threads * per_thread

    # Set max_size safely higher than total_keys to avoid shard evictions
    cache = SeverityCache(max_size=total_keys * 4, ttl_seconds=5, num_shards=32)
    cache.clear()
    cache.reset_stats()

    start_event = threading.Event()

    writers = []
    for i in range(num_threads):
        t = threading.Thread(target=worker_write, args=(cache, i * per_thread, (i + 1) * per_thread, start_event))
        writers.append(t)
        t.start()

    # Start all writers at once
    start_event.set()

    # Wait for writers to finish
    for t in writers:
        t.join()

    # Poll until all keys are visible or timeout
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if len(cache) >= total_keys:
            break
        time.sleep(0.01)

    stats = cache.get_stats()
    assert len(cache) >= total_keys, (
        f"Not all keys present after writers: len={len(cache)}, expected={total_keys}, stats={stats}"
    )

    # Spawn multiple reader threads that read overlapping key ranges
    readers = []
    keys = [f"k{j}" for j in range(total_keys)]
    # reuse a start event to begin readers at the same time
    read_start = threading.Event()
    for i in range(16):
        t = threading.Thread(target=worker_read, args=(cache, keys, read_start))
        readers.append(t)
        t.start()

    read_start.set()

    for t in readers:
        t.join()

    # Validate a sample of keys
    missing = 0
    for i in range(0, total_keys, 10):
        v = cache.get_severity(f"k{i}")
        if v is None:
            missing += 1

    if missing != 0:
        stats = cache.get_stats()
        raise AssertionError(f"Some keys missing after concurrent writes: {missing}, len={len(cache)}, stats={stats}")
