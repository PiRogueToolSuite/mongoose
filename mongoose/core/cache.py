import threading
import time
from collections import OrderedDict
from typing import Optional, Generic, TypeVar, Iterator, Dict, Any, List

from mongoose.core import SingletonMeta

K = TypeVar("K")
V = TypeVar("V")


class Cache(Generic[K, V], metaclass=SingletonMeta):
    """
    Sharded LRU cache with optional TTL implemented as a singleton per class.

    The cache partitions keys into a fixed number of shards. Each shard
    maintains its own OrderedDict and lock so operations for different
    shards can proceed concurrently without contending on a single global
    lock. Each shard enforces its own capacity (approximately
    max_size / num_shards), so the global max_size is a soft bound but
    should be close when keys distribute evenly.

    This design provides better concurrency for high-contention workloads
    while preserving LRU semantics within each shard.
    """

    def __init__(self, max_size: int = 1024, ttl_seconds: Optional[float] = None, num_shards: int = 1) -> None:
        """
        Initialize the sharded cache.

        Args:
            max_size: Global maximum number of entries (positive int).
            ttl_seconds: Optional TTL in seconds for entries. If None, no time expiry.
            num_shards: Number of independent shards to partition the keyspace.
        """
        # Guard against re-initialization when singleton returns an
        # already-created instance.
        if hasattr(self, "_initialized") and self._initialized:
            return

        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError("max_size must be a positive integer")
        if ttl_seconds is not None and (not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0):
            raise ValueError("ttl_seconds must be a positive number or None")
        if not isinstance(num_shards, int) or num_shards <= 0:
            raise ValueError("num_shards must be a positive integer")

        self.max_size: int = max_size
        self._ttl_seconds: Optional[float] = float(ttl_seconds) if ttl_seconds is not None else None

        # Ensure we don't create more shards than max_size (each shard should
        # have at least one slot when possible). Reducing shards avoids many
        # shards having zero capacity which would cause immediate eviction.
        self._num_shards: int = min(num_shards, max_size)

        # Compute per-shard max size; ensure at least 1 per shard when possible
        base = max_size // self._num_shards
        remainder = max_size % self._num_shards
        self._shard_max_sizes = [base + (1 if i < remainder else 0) for i in range(self._num_shards)]

        # Per-shard stores and locks
        self._shards: List[Dict[str, Any]] = []  # each shard: {'lock': RLock, 'store': OrderedDict}
        for i in range(self._num_shards):
            shard = {"lock": threading.RLock(), "store": OrderedDict()}
            self._shards.append(shard)

        # Stats counters for observability
        self._stats_lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

        self._initialized = True

    def _now(self) -> float:
        """Return current monotonic time."""
        return time.monotonic()

    def _expires_at(self) -> Optional[float]:
        """Return expiry timestamp for a new entry, or None if no TTL."""
        if self._ttl_seconds is None:
            return None
        return self._now() + self._ttl_seconds

    def _is_expired(self, expires_at: Optional[float]) -> bool:
        """Return True if the given expires_at timestamp is in the past."""
        return expires_at is not None and expires_at <= self._now()

    def _record_hit(self) -> None:
        with self._stats_lock:
            self._hits += 1

    def _record_miss(self) -> None:
        with self._stats_lock:
            self._misses += 1

    def _record_eviction(self) -> None:
        with self._stats_lock:
            self._evictions += 1

    def get_stats(self) -> Dict[str, int]:
        """Return current stats snapshot: hits, misses, evictions."""
        with self._stats_lock:
            return {"hits": self._hits, "misses": self._misses, "evictions": self._evictions}

    def reset_stats(self) -> None:
        """Zero all statistics."""
        with self._stats_lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def _shard_for_key(self, key: K) -> int:
        """Return the shard index for a given key."""
        return (hash(key) & 0x7FFFFFFF) % self._num_shards

    def _purge_expired_in_shard(self, shard_idx: int) -> None:
        """Purge expired entries from a single shard. Caller must hold shard lock."""
        if self._ttl_seconds is None:
            return
        now = self._now()
        store: OrderedDict = self._shards[shard_idx]["store"]
        remove = [k for k, (_v, expires_at) in store.items() if expires_at is not None and expires_at <= now]
        for k in remove:
            store.pop(k, None)

    def set(self, key: K, value: V) -> None:
        """
        Insert or update a key in its shard and enforce shard-level capacity.
        """
        shard_idx = self._shard_for_key(key)
        shard = self._shards[shard_idx]
        lock: threading.RLock = shard["lock"]
        with lock:
            store: OrderedDict = shard["store"]
            # Purge expired entries from this shard
            self._purge_expired_in_shard(shard_idx)

            if key in store:
                store.move_to_end(key)

            expires_at = self._expires_at()
            store[key] = (value, expires_at)

            # Evict LRU in this shard while over capacity
            shard_max = self._shard_max_sizes[shard_idx]
            while len(store) > shard_max:
                store.popitem(last=False)
                self._record_eviction()

    def get(self, key: K) -> Optional[V]:
        """
        Retrieve a key from its shard and mark it as recently used.

        Returns None if missing or expired.
        """
        shard_idx = self._shard_for_key(key)
        shard = self._shards[shard_idx]
        lock: threading.RLock = shard["lock"]
        with lock:
            store: OrderedDict = shard["store"]
            # Purge expired entries in shard
            self._purge_expired_in_shard(shard_idx)

            try:
                val, expires_at = store.pop(key)
            except KeyError:
                self._record_miss()
                return None

            if self._is_expired(expires_at):
                self._record_miss()
                return None

            # Re-insert to mark MRU in this shard
            store[key] = (val, expires_at)
            self._record_hit()
            return val

    def __len__(self) -> int:
        """Return the total number of non-expired items across all shards."""
        total = 0
        # Acquire shard locks in order to avoid deadlocks
        for i in range(self._num_shards):
            shard = self._shards[i]
            with shard["lock"]:
                self._purge_expired_in_shard(i)
                total += len(shard["store"])
        return total

    def clear(self) -> None:
        """Clear all shards."""
        for shard in self._shards:
            with shard["lock"]:
                shard["store"].clear()

    def __contains__(self, key: K) -> bool:
        """True if key exists and is not expired."""
        shard_idx = self._shard_for_key(key)
        shard = self._shards[shard_idx]
        with shard["lock"]:
            self._purge_expired_in_shard(shard_idx)
            return key in shard["store"]

    def items(self) -> Iterator[tuple[K, V]]:
        """Yield (key, value) pairs across shards (LRU within each shard)."""
        # Snapshot items from each shard while holding its lock
        snapshots = []
        for i in range(self._num_shards):
            shard = self._shards[i]
            with shard["lock"]:
                self._purge_expired_in_shard(i)
                snapshots.extend([(k, v) for k, (v, _e) in shard["store"].items()])
        for k, v in snapshots:
            yield (k, v)


class SeverityCache(Cache[str, int]):
    """
    Specialization of Cache for community_id -> severity mappings.

    Provides convenience methods `set_severity` and `get_severity` that
    validate input types and keep the simple, explicit API used by the
    rest of the codebase.
    """

    def set_severity(self, community_id: str, severity: int) -> None:
        """
        Store severity for a community_id. Always keep the highest severity
        value if the key already exists.

        This method performs the comparison and update under the shard
        lock to avoid extra cache hits and to ensure correctness under
        concurrent updates.

        Args:
            community_id: String identifier for the community.
            severity: Integer severity value.

        Raises:
            TypeError: If arguments are of incorrect types.
        """
        if not isinstance(community_id, str):
            raise TypeError("community_id must be a str")
        if not isinstance(severity, int):
            raise TypeError("severity must be an int")

        shard_idx = self._shard_for_key(community_id)
        shard = self._shards[shard_idx]
        lock: threading.RLock = shard["lock"]
        with lock:
            store: OrderedDict = shard["store"]
            # Purge expired entries in this shard first
            self._purge_expired_in_shard(shard_idx)

            existing = store.get(community_id)
            if existing is not None:
                existing_val, existing_expires = existing
                if existing_expires is not None and self._is_expired(existing_expires):
                    # Treat as missing
                    chosen = severity
                else:
                    chosen = max(existing_val, severity)
                # Move to MRU and set chosen value
                if community_id in store:
                    store.move_to_end(community_id)
                expires_at = self._expires_at()
                store[community_id] = (chosen, expires_at)
            else:
                expires_at = self._expires_at()
                store[community_id] = (severity, expires_at)

            # Evict LRU in this shard while over capacity
            shard_max = self._shard_max_sizes[shard_idx]
            while len(store) > shard_max:
                store.popitem(last=False)
                self._record_eviction()

    def get_severity(self, community_id: str) -> Optional[int]:
        """
        Retrieve the cached severity for a community_id or None if missing.

        Args:
            community_id: String identifier for the community.

        Returns:
            The severity integer if present, otherwise None.

        Raises:
            TypeError: If `community_id` is not a str.
        """
        if not isinstance(community_id, str):
            raise TypeError("community_id must be a str")

        return self.get(community_id)


def reset_singletons() -> None:
    """
    Clear the internal singleton instance registry.

    This is primarily intended for use in unit tests so different tests
    can instantiate singletons with different constructor parameters and
    get fresh instances. Use with care in production code as clearing
    singletons while other threads hold references can be unsafe.
    """
    with SingletonMeta._lock:
        SingletonMeta._instances.clear()
