# Auth & per-user rate limiting

`server_lux` already supported three auth modes via the Strategy/Factory pattern
(`AUTH_TYPE` = `token` | `auth0` | `none`). This adds a **per-user daily quota**
on the prediction endpoints (`/v1/run`, `/v1/run/detailed`, `/v1/simulate`), used
by the web daylight tool to cap free usage at 10 runs/day/user while the Revit
add-in stays unlimited.

> **Which endpoint?** The web tool predicts via **`/run`** (and `/run/detailed`
> in debug), not `/simulate`. Revit uses the same shared endpoints (`/run`,
> `/obstruction_all`, `/encode`), so the quota can't be scoped by URL — it is
> scoped by **Auth0 client id** instead (see below).
>
> **Two buckets** (separate counters, so a normal run's several supporting calls
> don't drain the prediction quota):
> - *Prediction* — `/run`, `/run/detailed`, `/simulate` → `RATE_LIMIT_PER_DAY` (10).
> - *Auxiliary compute* — obstruction / encode / stats / merge / direction /
>   reference-point / horizon / zenith → `RATE_LIMIT_AUX_PER_DAY` (generous
>   ceiling that only stops hammering; 0 disables it).

## Design

- **Identity**: the Auth0 strategy stashes the validated `sub` and `azp`
  (authorized-party = client id) into `flask.g` (`g.auth_subject`,
  `g.auth_client_id`). `RequestIdentityResolver` keys the quota on `sub:<id>`,
  falling back to `ip:<addr>` when no subject is present.
- **Per-app scope**: when `RATE_LIMIT_CLIENT_ID` is set, only requests from that
  Auth0 client (the web app) are counted; every other client (the Revit add-in)
  passes through unlimited — even on the same `/run` endpoint. Empty ⇒ limit all.
- **Counter**: `INCR` on a Redis key with a one-shot `EXPIRE` set on the first
  hit, so the key self-clears `RATE_LIMIT_WINDOW_HOURS` (24 h) after that first
  request — a fixed **rolling window**, not a calendar day (no midnight boundary
  to double up on). Atomic ⇒ correct across workers/instances (check-by-increment,
  no read-modify-write race).
- **Decorator order** in `main.py`: `auth(quota(handler))` — authentication runs
  first and sets the subject/client id the quota keys and gates on.
- **Disabled** (`RATE_LIMIT_ENABLED=false`, the default): `require_quota` returns
  the handler unchanged — zero overhead. `redis` is a hard dependency
  (`requirements.txt`) either way, so nothing is skipped at import time; this
  just avoids ever touching Redis at runtime.

## Files

| File | Responsibility |
|------|----------------|
| `rate_limit_config.py` | `RateLimitConfig` (immutable, from env) |
| `rate_limit_store.py` | `RateLimitStore` + Redis/InMemory/Null (rolling-window TTL) + factory |
| `rate_limiter.py` | `RateLimiter.require_quota` decorator + identity resolver + client-id gate |
| `auth_strategies.py` | Auth0 strategy now exposes `g.auth_subject` + `g.auth_client_id` |

## Configuration

| Env var | Default | Meaning |
|---------|---------|---------|
| `RATE_LIMIT_ENABLED` | `false` | Master switch. |
| `RATE_LIMIT_PER_DAY` | `10` | Prediction requests (/run, /run/detailed, /simulate) per rolling window. |
| `RATE_LIMIT_WINDOW_HOURS` | `24` | Rolling window length (the counter's TTL). |
| `RATE_LIMIT_AUX_PER_DAY` | `300` | Ceiling for supporting compute endpoints (obstruction/encode/stats/…). 0 = off. |
| `RATE_LIMIT_REDIS_URL` | — | Redis/Valkey URL (falls back to `REDIS_URL`). In compose, defaults to the co-located `redis` service. |
| `RATE_LIMIT_KEY_PREFIX` | `lux:quota` | Redis key namespace. |
| `RATE_LIMIT_CLIENT_ID` | — | Auth0 client id the quota applies to (the web app). Empty = limit everyone. Set it so Revit stays unlimited. |
| `RATE_LIMIT_TRUSTED_PROXY_HOPS` | `0` | Reverse proxies appending to `X-Forwarded-For` (nginx + Cloudflare = 2). 0 = don't trust the header. |

The compose files ship a co-located `redis` service (no persistence) and default
`RATE_LIMIT_REDIS_URL` to it, so the counter is shared across gunicorn workers on
the box. Point it at an external Managed Redis (`rediss://`) only for multi-host.
Without any Redis URL the limiter falls back to an **in-memory** store
(process-local, not shared across workers) and logs a warning — local/dev only.

## Response contract

Success responses carry informational headers:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 2026-08-15T09:42:00+00:00
```

When the quota is spent, `429 Too Many Requests`:

```json
{
  "status": "error",
  "error": "Request limit reached. Try again after the reset time.",
  "error_type": "rate_limit_exceeded",
  "limit": 10,
  "remaining": 0,
  "reset_at": "2026-08-15T09:42:00+00:00"
}
```

The web tool maps `429` → `QuotaExceededError` (localised message with reset
time) and `401/403` → `AuthRequiredError` (prompt login).

## Scaleway Managed Redis

1. Create a **Managed Database for Redis®** (Valkey) in `fr-par`, smallest node.
2. Put its `rediss://` URL in `RATE_LIMIT_REDIS_URL` as a Serverless Container
   secret (never commit it).
3. Restrict access to the container's private network / ACL.
4. Memory need is tiny (one small integer per active user per day, auto-expiring)
   — the smallest instance is plenty.

## Tests

`tests/server/test_rate_limiter.py` covers: allow-up-to-limit-then-block,
per-subject isolation, disabled passthrough, IP fallback, subject-over-IP
precedence, and the day-window reset math. Uses the in-memory store, no Redis
needed. Run:

```bash
python3 -m pytest tests/server/test_rate_limiter.py -q
```
