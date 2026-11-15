"""TTL cache with per-key single-flight and stale-if-error."""
from __future__ import annotations

import threading
import time


MAX_KEYS = 256
MAX_AGE_S = 900


class TTLCache:
    def __init__(self, clock=time.monotonic, max_keys: int = MAX_KEYS):
        self._max = max_keys
        self._clock = clock
        self._data: dict = {}
        self._locks: dict = {}
        self._guard = threading.Lock()

    def _lock(self, key):
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def peek(self, key):
        hit = self._data.get(key)
        return hit[0] if hit else None

    def clear(self):
        with self._guard:
            self._data.clear()

    def get_or_fetch(self, key, ttl: float, fn, stale_ok_s: float = 300):
        """Return (value, stale). One caller per key runs fn; the rest wait and reuse its result.

        If fn raises and an entry no older than ttl + stale_ok_s exists, that entry comes back with stale=True.
        """
        hit = self._data.get(key)
        if hit and self._clock() - hit[1] < ttl:
            return hit[0], False
        with self._lock(key):
            hit = self._data.get(key)
            if hit and self._clock() - hit[1] < ttl:
                return hit[0], False
            try:
                value = fn()
            except Exception:
                if hit and self._clock() - hit[1] < ttl + stale_ok_s:
                    return hit[0], True
                raise
            self._data[key] = (value, self._clock())
            self._prune()
            return value, False

    def _prune(self):
        if len(self._data) <= self._max:
            return
        with self._guard:
            now = self._clock()
            for k in [k for k, v in self._data.items() if now - v[1] > MAX_AGE_S]:
                del self._data[k]
            for k in sorted(self._data, key=lambda k: self._data[k][1])[:max(0, len(self._data) - self._max)]:
                del self._data[k]
            for k in [k for k, lk in self._locks.items() if k not in self._data and not lk.locked()]:
                del self._locks[k]
