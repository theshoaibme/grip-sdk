"""Token-bucket rate limiter keyed by client identifier."""

import threading
import time


class TokenBucket:
    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._tokens = float(capacity)
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._updated = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def retry_after(self) -> float:
        with self._lock:
            if self._tokens >= 1:
                return 0.0
            deficit = 1 - self._tokens
            return round(deficit / self.refill_per_sec, 2)


class RateLimiter:
    """Maintains token buckets per client IP with an optional global bucket."""

    def __init__(
        self,
        capacity: int = 30,
        refill_per_sec: float = 1.0,
        global_capacity: int | None = None,
    ) -> None:
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._global = (
            TokenBucket(global_capacity, refill_per_sec)
            if global_capacity is not None
            else None
        )

    def _bucket_for(self, key: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(self.capacity, self.refill_per_sec)
                self._buckets[key] = bucket
            return bucket

    def check(self, key: str) -> tuple[bool, float]:
        """Check if request from client is allowed. Returns (allowed, retry_after_sec)."""
        bucket = self._bucket_for(key)
        if self._global is not None and not self._global.consume():
            return False, self._global.retry_after()
        if not bucket.consume():
            return False, bucket.retry_after()
        return True, 0.0
