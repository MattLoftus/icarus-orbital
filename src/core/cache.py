"""Simple in-memory LRU cache for API results."""

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Optional


class ResultCache:
    """Thread-unsafe LRU cache with optional TTL.

    Designed for caching expensive computation results (Lambert solutions,
    porkchop plot grids, etc.) within a single process.
    """

    def __init__(self, max_size: int = 100, ttl_seconds: Optional[float] = None):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value by key. Returns None on miss."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        # Check TTL expiry
        if self._ttl_seconds is not None:
            age = time.monotonic() - entry["timestamp"]
            if age > self._ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache, evicting the oldest entry if full."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = {"value": value, "timestamp": time.monotonic()}
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = {"value": value, "timestamp": time.monotonic()}

    def make_key(self, **kwargs) -> str:
        """Hash keyword arguments into a deterministic cache key.

        Serializes kwargs to sorted JSON and returns a SHA-256 hex digest.
        All values must be JSON-serializable.
        """
        raw = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def clear(self) -> None:
        """Remove all entries and reset statistics."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)

    @property
    def stats(self) -> dict:
        """Return hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": len(self._cache),
            "max_size": self._max_size,
        }

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def __repr__(self) -> str:
        return f"ResultCache(size={len(self._cache)}, max_size={self._max_size})"


# ---------------------------------------------------------------------------
# Global cache instances
# ---------------------------------------------------------------------------

# Lambert / transfer orbit solutions — moderate size, reused often
transfer_cache = ResultCache(max_size=200)

# Porkchop plot grids — large objects, keep fewer
porkchop_cache = ResultCache(max_size=20)
