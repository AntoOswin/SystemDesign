"""Unit tests for rate_limiter.

Run with:
    python -m pytest test_rate_limiter.py -v
or:
    python -m unittest test_rate_limiter.py
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import List

from rate_limiter import CreditRateLimiter, InMemoryRateLimiter, TokenBucket


class FakeClock:
    """Deterministic, advanceable clock for tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.t

    def advance(self, seconds: float) -> None:
        with self._lock:
            self.t += seconds


class TestTokenBucket(unittest.TestCase):
    def test_initial_capacity_full(self) -> None:
        bucket = TokenBucket(capacity=5, refill_rate=1)
        for _ in range(5):
            self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)

    def test_refill_over_time(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(capacity=10, refill_rate=2, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)

        clock.advance(3)  # 3s * 2 tokens/s = 6 tokens refilled.
        for _ in range(6):
            self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)

    def test_refill_caps_at_capacity(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(capacity=5, refill_rate=10, clock=clock)
        clock.advance(1000)
        for _ in range(5):
            self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)

    def test_retry_after_reported(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(capacity=1, refill_rate=2, clock=clock)
        self.assertTrue(bucket.allow().allowed)
        d = bucket.allow()
        self.assertFalse(d.allowed)
        self.assertAlmostEqual(d.retry_after, 0.5, places=6)

    def test_burst_then_steady_state(self) -> None:
        clock = FakeClock()
        bucket = TokenBucket(capacity=100, refill_rate=10, clock=clock)
        for _ in range(100):
            self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)
        for _ in range(5):
            clock.advance(1.0)
            for _ in range(10):
                self.assertTrue(bucket.allow().allowed)
            self.assertFalse(bucket.allow().allowed)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            TokenBucket(capacity=0, refill_rate=1)
        with self.assertRaises(ValueError):
            TokenBucket(capacity=1, refill_rate=0)
        bucket = TokenBucket(capacity=1, refill_rate=1)
        with self.assertRaises(ValueError):
            bucket.allow(0)


class TestInMemoryRateLimiter(unittest.TestCase):
    def test_independent_buckets_per_client(self) -> None:
        clock = FakeClock()
        rl = InMemoryRateLimiter(capacity=2, refill_rate=1, clock=clock)
        self.assertTrue(rl.allow("alice").allowed)
        self.assertTrue(rl.allow("alice").allowed)
        self.assertFalse(rl.allow("alice").allowed)
        self.assertTrue(rl.allow("bob").allowed)
        self.assertTrue(rl.allow("bob").allowed)
        self.assertFalse(rl.allow("bob").allowed)


class TestCreditRateLimiter(unittest.TestCase):
    def test_unused_credits_roll_over(self) -> None:
        clock = FakeClock()
        cl = CreditRateLimiter(
            refill_rate=1, credit_cap=100, initial_credits=0, clock=clock
        )
        clock.advance(50)  # earn 50 credits.
        for _ in range(50):
            self.assertTrue(cl.allow().allowed)
        self.assertFalse(cl.allow().allowed)

    def test_credits_capped(self) -> None:
        clock = FakeClock()
        cl = CreditRateLimiter(
            refill_rate=10, credit_cap=20, initial_credits=0, clock=clock
        )
        clock.advance(1000)
        for _ in range(20):
            self.assertTrue(cl.allow().allowed)
        self.assertFalse(cl.allow().allowed)

    def test_sustained_rate_after_burst(self) -> None:
        clock = FakeClock()
        cl = CreditRateLimiter(
            refill_rate=5, credit_cap=10, initial_credits=10, clock=clock
        )
        for _ in range(10):
            self.assertTrue(cl.allow().allowed)
        self.assertFalse(cl.allow().allowed)
        for _ in range(10):
            clock.advance(1.0)
            for _ in range(5):
                self.assertTrue(cl.allow().allowed)
            self.assertFalse(cl.allow().allowed)


class TestConcurrency(unittest.TestCase):
    """Stress test: the most important test for a rate limiter."""

    def test_no_race_under_contention(self) -> None:
        capacity = 100
        # Tiny refill so no appreciable refill happens during the test.
        bucket = TokenBucket(capacity=capacity, refill_rate=1e-9)

        accepted: List[int] = []
        accepted_lock = threading.Lock()
        threads = []
        n_threads = 50
        per_thread = 1000

        def worker() -> None:
            local_accepted = 0
            for _ in range(per_thread):
                if bucket.allow().allowed:
                    local_accepted += 1
            with accepted_lock:
                accepted.append(local_accepted)

        for _ in range(n_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        total = sum(accepted)
        self.assertEqual(
            total, capacity,
            f"Expected exactly {capacity} accepted across {n_threads} threads, "
            f"got {total}. Concurrency bug!"
        )

    def test_concurrent_clients_isolated(self) -> None:
        rl = InMemoryRateLimiter(capacity=10, refill_rate=1e-9)
        accepted_per_client = {"a": 0, "b": 0, "c": 0}
        lock = threading.Lock()

        def worker(key: str) -> None:
            local = 0
            for _ in range(500):
                if rl.allow(key).allowed:
                    local += 1
            with lock:
                accepted_per_client[key] += local

        threads = []
        for key in ("a", "b", "c"):
            for _ in range(10):
                t = threading.Thread(target=worker, args=(key,))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()

        for k, v in accepted_per_client.items():
            self.assertEqual(
                v, 10,
                f"Client {k}: expected 10 accepted, got {v}. "
                f"Counters leaked across clients!"
            )


class TestRealClockSmokeTest(unittest.TestCase):
    def test_real_refill(self) -> None:
        bucket = TokenBucket(capacity=2, refill_rate=20)
        self.assertTrue(bucket.allow().allowed)
        self.assertTrue(bucket.allow().allowed)
        self.assertFalse(bucket.allow().allowed)
        time.sleep(0.2)
        self.assertTrue(bucket.allow().allowed)
        self.assertTrue(bucket.allow().allowed)


if __name__ == "__main__":
    unittest.main()
