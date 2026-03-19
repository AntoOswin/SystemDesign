# System Design Interview Study Guide — Overview

## How to Use These Notes

Each file follows the **exact same structure** so you can practice consistently:

1. **Read the problem statement** — understand what you're building and for whom.
2. **Start with the naive design** — this is how you should open in an interview.
3. **Walk through the bottlenecks** — show the interviewer you know what breaks.
4. **Evolve toward the final design** — each change should solve a specific problem.
5. **Review the interview checklist** — make sure you can say each point out loud.

---

## Interview Framework (Use This Every Time)

```
1. Clarify requirements          (2 min)
2. Estimate scale                (1 min)
3. Define API                    (2 min)
4. Draw high-level design        (5 min)
5. Deep-dive into components     (15 min)
6. Address bottlenecks & trade-offs (5 min)
7. Wrap up with reliability & security (3 min)
```

**Say this out loud at the start of every problem:**
> "Before I start designing, let me clarify the requirements, estimate scale, and then walk through the architecture step by step."

---

## Common Vocabulary

Keep these definitions handy. Every file uses them consistently.

| Term | Plain English | Why It Matters |
|------|--------------|----------------|
| **Load Balancer (LB)** | A traffic cop that spreads incoming requests across multiple servers | Without it, one server gets all the traffic and crashes |
| **API Gateway** | A single front door that handles auth, rate limiting, and routing before requests hit your services | Keeps cross-cutting concerns in one place |
| **CDN (Content Delivery Network)** | Copies of your static files stored on servers close to users around the world | Reduces latency; users download from a nearby server instead of your origin |
| **Cache** | A fast temporary store (usually in memory) for data you read often | Avoids hitting the database on every request |
| **Message Queue** | A buffer between producers and consumers — the producer drops a message, the consumer picks it up later | Decouples services and absorbs traffic spikes |
| **Event Stream** | A durable, ordered log of events that multiple consumers can read independently | Good for event-driven architectures and replay |
| **Relational DB (RDBMS)** | A database with tables, rows, columns, and strong consistency (e.g., PostgreSQL, MySQL) | Best when you need ACID transactions and complex queries |
| **NoSQL** | A broad category of databases that trade some consistency or query flexibility for scale (e.g., DynamoDB, Cassandra, MongoDB) | Best for high write throughput or flexible schemas |
| **Object Storage** | A service for storing large blobs — files, images, videos (e.g., S3, Azure Blob) | Cheap, durable, and designed for large files, not queries |
| **Sharding / Partitioning** | Splitting data across multiple database instances by some key (user ID, region, etc.) | Lets you scale writes beyond a single machine |
| **Read Replica** | A copy of the database that handles read queries, reducing load on the primary | Scales reads without touching write path |
| **Idempotency** | Doing the same operation twice produces the same result (no duplicates) | Critical for retries — you can safely retry without side effects |
| **Rate Limiting** | Capping how many requests a user or IP can make in a time window | Prevents abuse and protects backend services |
| **Circuit Breaker** | A pattern that stops calling a failing service and fails fast instead | Prevents cascade failures when a dependency is down |
| **Dead-Letter Queue (DLQ)** | A special queue where failed messages go after too many retries | Lets you investigate failures without blocking the main queue |
| **Backpressure** | When a system slows down or rejects work because it can't keep up | Prevents overload by pushing back on the producer |
| **Eventual Consistency** | Data will be consistent across all nodes, but not instantly — there's a short delay | Trade-off for higher availability and lower latency |
| **Strong Consistency** | Every read returns the most recent write — no stale data | Required for things like payments and seat reservations |
| **TTL (Time To Live)** | How long a cached value or record is valid before it expires | Controls freshness vs. performance trade-off |
| **Pub/Sub (Publish-Subscribe)** | A messaging pattern where publishers send messages to a topic, and all subscribers receive them | Good for fan-out: one event triggers multiple actions |
| **WebSocket** | A persistent, two-way connection between client and server | Enables real-time push without polling |
| **Long Polling** | The client makes a request and the server holds it open until there's new data | Simpler than WebSockets but less efficient |
| **Adaptive Bitrate (ABR)** | The video player automatically switches quality based on network speed | Prevents buffering on slow connections |
| **ACID** | Atomicity, Consistency, Isolation, Durability — guarantees for database transactions | Ensures correctness for financial and booking systems |
| **BASE** | Basically Available, Soft state, Eventual consistency — the NoSQL trade-off | Prioritizes availability over immediate consistency |

---

## File Index

| File | System | Key Skills Practiced |
|------|--------|---------------------|
| `01-bulk-emailing.md` | Bulk Email Service | Async processing, idempotency, queues, bounce handling |
| `02-netflix-video-streaming.md` | Netflix / VOD | CDN, encoding, adaptive bitrate, control vs data plane |
| `03-weather-system.md` | Weather Service | Data ingestion, caching, freshness, geo queries |
| `04-ticketmaster-event-ticketing.md` | Ticketmaster | Concurrency, distributed locking, oversell prevention |
| `05-messenger-chat-system.md` | Messenger / Chat | WebSockets, ordering, presence, offline sync |
| `06-spotify-music-player.md` | Spotify / Music | Metadata vs media storage, CDN, search, playlists |
| `07-scalable-web-app.md` | Scalable Web App | Ground-up architecture, DB, cache, queues, replicas |
| `08-live-streaming-platform.md` | Live Streaming (Twitch) | Real-time ingest, chunking, low-latency delivery |
| `09-notification-service.md` | Notification Service | Multi-channel fan-out, delivery tracking, SaaS patterns |

---

## Universal Interview Tips

1. **Always start simple.** Draw a single box, a single database. Then grow.
2. **Name your scale.** "Let's assume 10M users, 1K requests/sec" — this drives every decision.
3. **Every component must justify its existence.** If you add a cache, say what it caches and why.
4. **Talk about trade-offs, not perfection.** "This adds complexity but solves X."
5. **Use numbers.** "A row is ~200 bytes, 100M rows = ~20 GB — fits on one machine."
6. **Mention failure modes.** "If this service goes down, the queue buffers requests until it recovers."
7. **End with what you'd monitor.** "I'd track p99 latency, error rate, and queue depth."

---

## Back-of-the-Envelope Cheat Sheet

| Quantity | Value |
|----------|-------|
| 1 million seconds | ~11.5 days |
| 1 billion seconds | ~31.7 years |
| Read from memory | ~100 ns |
| Read from SSD | ~100 μs |
| Read from disk | ~10 ms |
| Send 1 KB over network (same DC) | ~250 μs |
| Send 1 KB over network (cross-continent) | ~150 ms |
| 1 KB × 1M users | 1 GB |
| 1 MB × 1M users | 1 TB |
| QPS for a single web server | ~1K–10K |
| QPS for a single DB (PostgreSQL) | ~5K–20K reads, ~1K–5K writes |
| QPS for Redis | ~100K+ |

---

## How to Talk About Each Layer

| Layer | What to Say |
|-------|-------------|
| **Client** | "The client sends a request to..." |
| **Load Balancer** | "Traffic is distributed across N app servers via a load balancer..." |
| **API Gateway** | "The gateway handles auth, rate limiting, and routes to the correct service..." |
| **Application Service** | "This service handles the business logic for X..." |
| **Cache** | "Before hitting the DB, we check the cache. Cache hit ratio is ~90%, so this cuts DB load by 10×..." |
| **Database** | "We store X in PostgreSQL because we need transactions / We use DynamoDB because we need high write throughput..." |
| **Queue** | "This operation is async — we enqueue it and a worker processes it, which decouples the write path from the API response..." |
| **Object Storage** | "Large files go to S3/Blob storage — the DB only stores the URL/metadata..." |
| **CDN** | "Static assets are served from CDN edge nodes closest to the user..." |
