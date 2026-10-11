"""Token bucket rate limiting."""

from __future__ import annotations

from google_ai_search.core.ratelimit import RateLimiter as _BaseRateLimiter, TokenBucket as _BaseTokenBucket


class TokenBucket(_BaseTokenBucket):
    """TokenBucket avoiding ZeroDivisionError when refill_per_sec <= 0."""

    def retry_after(self) -> float:
        with self._lock:
            if self._tokens >= 1:
                return 0.0
            deficit = 1 - self._tokens
            if self.refill_per_sec <= 0:
                return 60.0
            return round(deficit / self.refill_per_sec, 2)


class RateLimiter(_BaseRateLimiter):
    """Token bucket rate limiter with safe division and acquire() method."""

    def _bucket_for(self, key: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(self.capacity, self.refill_per_sec)
                self._buckets[key] = bucket
            return bucket

    def acquire(self, key: str) -> bool:
        allowed, _ = self.check(key)
        return allowed


__all__ = ["RateLimiter", "TokenBucket"]
