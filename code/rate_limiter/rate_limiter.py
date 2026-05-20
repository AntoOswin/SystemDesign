"""
Thread-safe rate limiter implementations.

Includes:
  * TokenBucket           - canonical token-bucket with burst capacity.
  * InMemoryRateLimiter   - manages many client buckets with lock striping.
  * CreditRateLimiter     - explicit credit-rollover variant with a hard cap.

Designed to be safe under high concurrency. The critical section in each
allow() call is intentionally tiny so that lock contention is negligible
for typical workloads (tens of thousands of QPS per process).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional


Clock = Callable[[], float]


@dataclass
class Decision:
    allowed: bool
    remaining: float
    retry_after: float  # seconds until at least one token will be available


class TokenBucket:
    """A single token bucket. Thread-safe.

    capacity     - maximum number of tokens (max burst size).
    refill_rate  - tokens added per second.
    clock        - injected for deterministic tests; defaults to time.monotonic.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        clock: Clock = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._clock = clock
        self._tokens = float(capacity)
        self._last_refill = clock()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(
                self.capacity, self._tokens + elapsed * self.refill_rate
            )
            self._last_refill = now

    def allow(self, n: float = 1.0) -> Decision:
        """Try to consume n tokens. Returns (allowed, remaining, retry_after)."""
        if n <= 0:
            raise ValueError("n must be > 0")
        with self._lock:
            self._refill_locked()
            if self._tokens >= n:
                self._tokens -= n
                return Decision(True, self._tokens, 0.0)
            deficit = n - self._tokens
            retry_after = deficit / self.refill_rate
            return Decision(False, self._tokens, retry_after)

    @property
    def tokens(self) -> float:
        with self._lock:
            self._refill_locked()
            return self._tokens


class InMemoryRateLimiter:
    """Manages a TokenBucket per client key.

    Uses a single lock for the dict (creation is rare); each bucket has
    its own lock so per-client throughput scales with cores.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock
        self._buckets: Dict[str, TokenBucket] = {}
        self._creation_lock = threading.Lock()

    def _get_bucket(self, key: str) -> TokenBucket:
        b = self._buckets.get(key)
        if b is not None:
            return b
        with self._creation_lock:
            b = self._buckets.get(key)
            if b is None:
                b = TokenBucket(self.capacity, self.refill_rate, self._clock)
                self._buckets[key] = b
            return b

    def allow(self, key: str, n: float = 1.0) -> Decision:
        return self._get_bucket(key).allow(n)


class CreditRateLimiter:
    """Credit-based rate limiter.

    Semantics: a client earns `refill_rate` credits per second up to a
    hard cap of `credit_cap`. Each request consumes one credit. Unused
    credits roll over indefinitely (bounded by credit_cap).

    This is functionally a token bucket where capacity == credit_cap.
    It is exposed as a separate type so the credit-based contract is
    explicit at the API boundary.
    """

    def __init__(
        self,
        refill_rate: float,
        credit_cap: float,
        initial_credits: Optional[float] = None,
        clock: Clock = time.monotonic,
    ) -> None:
        if credit_cap <= 0:
            raise ValueError("credit_cap must be > 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        if initial_credits is None:
            initial_credits = credit_cap
        if not (0 <= initial_credits <= credit_cap):
            raise ValueError("initial_credits must be in [0, credit_cap]")

        self.refill_rate = refill_rate
        self.credit_cap = credit_cap
        self._clock = clock
        self._credits = float(initial_credits)
        self._last_refill = clock()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._credits = min(
                self.credit_cap, self._credits + elapsed * self.refill_rate
            )
            self._last_refill = now

    def allow(self, n: float = 1.0) -> Decision:
        with self._lock:
            self._refill_locked()
            if self._credits >= n:
                self._credits -= n
                return Decision(True, self._credits, 0.0)
            deficit = n - self._credits
            return Decision(False, self._credits, deficit / self.refill_rate)

    @property
    def credits(self) -> float:
        with self._lock:
            self._refill_locked()
            return self._credits
