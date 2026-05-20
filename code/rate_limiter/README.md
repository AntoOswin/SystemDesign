# Rate Limiter — Reference Implementation

Companion code for `../../11-rate-limiter.md`.

## Files
- `rate_limiter.py` — `TokenBucket`, `InMemoryRateLimiter`, `CreditRateLimiter`.
- `test_rate_limiter.py` — unit tests covering basic behavior, refill, credit rollover, and concurrency.

## Running the tests

With pytest:
```bash
python -m pytest test_rate_limiter.py -v
```

With the standard library only:
```bash
python -m unittest test_rate_limiter.py -v
```

The concurrency test (`TestConcurrency.test_no_race_under_contention`) is the most important — it runs 50 threads × 1000 requests against a bucket with capacity 100 and asserts that exactly 100 requests are accepted. If a race condition exists, this test will report > 100 accepted.

## Why these classes
- `TokenBucket` — the core algorithm. Thread-safe via a per-bucket lock.
- `InMemoryRateLimiter` — manages a `TokenBucket` per client key. Bucket creation uses double-checked locking; per-client throughput is independent.
- `CreditRateLimiter` — the credit-rollover variant required by the interview follow-up. Functionally equivalent to a token bucket; exposed as a distinct type so the API contract ("credits roll over up to a cap") is explicit.
