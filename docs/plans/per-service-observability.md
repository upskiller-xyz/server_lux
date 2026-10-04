# Plan: per-service call tracking, centralized, with a weekly report

## Problem

`StageTimer` (`src/server/services/helpers/timing.py`) wraps whole stages —
`controller.run`, `orchestrator.run` — as one lump each
(`request_handler.py:160-165`, `endpoint_controller.py:41-48`). It answers
"how long did the request take" but not "where did the 7–8 seconds go":
encoder, obstruction, merger, stats and Modal are all inside the
`orchestrator.run` span with no further breakdown.

A Modal dashboard export (`log.md`, 500 calls, 18 Sep – 4 Oct) answered the
"where" question for Modal specifically, and the answer was unexpected: the
GPU inference itself is sub-second (p50 execution 0.27s). The queue before it
is the real cost (p99 190s, 3.4% of calls over 60s, one four-minute stall on
24 Sep) — and that queueing is Modal-side capacity allocation, not something
visible from inside `server_lux` at all. That finding is *why* this plan
exists: Modal is ruled out as the source of the 7-8s felt end-to-end, which
means the answer is in encoder, obstruction, merger, or the orchestration
itself — and nothing today can show which.

## Design: three layers, kept separate

**Emit (deterministic).** Each outbound call writes one structured line.
**Reduce (deterministic, committed, tested).** A script turns a window of
emitted lines into percentiles, error rates, deltas — numbers, not prose.
**Interpret (the model, later).** Only the *reduced* numbers get compared
against stated budgets and written up.

The reason to keep these separate, and specifically to keep the model away
from raw logs: a model asked to eyeball a pile of JSONL will produce
plausible-sounding numbers that are not reliably the real percentiles. A
script that computes p50/p90/p99 from the data is either right or has a bug
that shows up in its tests. Push everything that has one correct answer into
code; keep the model for the part that actually requires judgment — deciding
whether a deviation matters and what to do about it.

## Step 1: `[call]` records at the outbound call sites — **DONE (PR #94)**

**Correction to the first write-up: it is five call sites, not three.** The
original table missed two — and one of them is the heaviest call in the
pipeline:

| Site | Used by |
|---|---|
| `base.py:107` (`run`) | encoder, merger, stats, obstruction |
| `base.py:144` (`run_binary`) | binary-response endpoints |
| `model_service.py:64` (`run`) | **Modal** |
| `obstruction_service.py:149` (`_run_binary` → `post_multipart`) | **the binary mesh transport — the multi-MB payload path** |
| `model_spec_service.py:33` (`get`) | `/spec` |

Instrumenting only the original three would have silently dropped the most
expensive obstruction calls (the `_bin` route) and every spec fetch.

A `CallRecorder`, shaped like `StageTimer` so it reads as the same pattern,
wraps each call and emits one JSON line:

```
{"ts": ..., "rid": "...", "service": "encoder", "endpoint": "/encode", "ms": 842, "outcome": "ok"}
```

**Service name must come from `cls.name` (the `ServiceName` enum each
`RemoteService` subclass sets), not from the URL.**
`HTTPClient._parse_service_name` takes the URL's first path segment — for
`http://encoder-service:8082/encode` that returns `"encode"`, and for Modal's
`.../predict` it returns `"predict"`. It is already misnamed and already
produces wrong labels in today's error messages; worth fixing on its own
regardless of this plan, but definitely don't build the new recorder on top
of it.

**`rid` (a request id) is what turns this into tracing rather than just
counters.** nginx already generates `$request_id`; forward it as
`X-Request-Id`, read it into the request context, and stamp every `[call]`
line with it. That makes it possible to pull one pipeline run's full
breakdown out of the log, not just aggregate percentiles. Do this alongside
the `log_format` change already planned for the nginx access log (adding
`rt=$request_time` / `urt=$upstream_response_time`) — same piece of nginx
config work, same motivation (today's access log has no timing and no
correlation id).

Two things the review of PR #94 added, both now part of the implementation:

- **The rid is attacker-controlled input** (in direct deployments without the
  gateway, any client sets it) that lands in every `[call]` record — where the
  per-window fan-out multiplies it. It is sanitized with the existing
  telemetry `HeaderValueSanitizer` before use: control characters stripped
  (log forging), 128-char cap (log amplification), control-only collapses to
  `"-"`.
- **`X-Request-Id` must be in CORS `EXPOSED_HEADERS`** or browsers hide it
  from the web app — and a client-side report that can't read the id can't
  join on it.

**Known gap, deliberately not in step 1:** lux does not forward the rid on
its *outbound* calls (`_auth_headers` carries auth only), so the services
(encoder, obstruction, merger, stats) cannot correlate even if they wanted
to. The lux-side records see each hop from the caller's side, which answers
"which hop is slow"; per-service instrumentation is worth adding only when
the reduce output names the service that needs it (the recorder is a
self-contained helper, trivial to port). Forwarding the rid outbound is a
small change that unlocks the per-service half later without touching the
five repos now.

## Step 2: fix the thread pools before any of this matters — **DONE (PR #94)**

**Correction to the first write-up: there are two fan-outs, not one.**
`window_processor.py:66-75` (per-window) *and*
`service_executor.py:49` (`ParallelServiceExecutor` — the reference-point /
obstruction fan-out) both used `loop.run_in_executor(None, ...)`.
**`run_in_executor` does not propagate context to the worker thread** — a
span or correlation id set as a contextvar on the calling thread will not be
visible inside the executor thread. Every span created inside either
fan-out would become a disconnected root instead of a child of the request's
span, producing N unrelated trace fragments per run instead of one tree.

Fix: switch both to `asyncio.to_thread(...)`, which copies the context via
`contextvars.copy_context()`. One-line change per site, no behavior
difference beyond fixing the context propagation, and it is a prerequisite
for `rid` correlation to actually work across the fan-outs — not just for
OpenTelemetry later.

This also matters for the CI/CD-adjacent question of how much CPU the
encoder needs: a single request can fan out to up to 39 windows (seen in the
Modal log's call clustering), each one a parallel call to encoder/Modal/etc.
Correct correlation is what lets a reduced report say "this request's 39
windows took this much wall time in encoder, in total" instead of 39
unconnected numbers.

## Step 3: ship Modal into the same data, not around it

Modal is the one hop that cannot be instrumented from inside `server_lux` —
the breakdown (queue / startup / execution) that mattered for the Modal
finding above only exists in Modal's own system. Two paths, in order of
preference:

1. **Propagate `traceparent` into the Modal app** and have the function emit
   its own `[call]`-shaped records (or real spans, if on OpenTelemetry by
   then) for queue/startup/execution. This is the only path that gives
   per-run linkage between a `server_lux` request and its Modal breakdown.
   Requires touching the Modal app's own code, which is owned here, so it's
   achievable — just not from `server_lux` alone.
2. **Pull from Modal's dashboard/API in the reduce step** and join by
   timestamp. Cheaper to build, no per-run linkage, good enough for weekly
   aggregate reporting (percentiles, cold-start rate, queue-incident
   detection) but can't answer "which request waited 190s."

Do (2) first if a weekly report is wanted sooner; do (1) when ready to also
want traceparent-correlated traces per run.

## Step 4: one place to put all of it

**JSONL to Object Storage, one file per day.** Credentials already exist
(`SCW_ACCESS_KEY` / `SCW_SECRET_KEY` / `SCW_ENDPOINT_URL` — used for the model
bucket in the full-stack setup; optional in the Scaleway stack, so this step
adds them to that deploy) and no new infrastructure is needed. At this
volume (roughly 8 runs/day, a handful of calls each) a week of data is a few
hundred kilobytes.

Until this step is built, the records live only in container stdout
(`docker logs` / `docker compose logs`), so they reset on every deploy — the
same discontinuity the deploy marker (step 5) exists to explain.

Why not push straight into an observability backend (Cockpit, Tempo,
Prometheus): a flat file is readable by a reduce script with no API keys, no
query language, and no backend-specific client library — which matters
because the weekly agentic job (step 6) needs to read this data cheaply and
reliably. A backend becomes the right call once there's a UI need (clicking
through a waterfall view for hundreds of runs); at the current volume `awk`
over a day's file is faster than that UI would be anyway.

## Step 5: a deploy marker in the same stream

After the "Copy env and deploy over SSH" step succeeds in
`deploy-scaleway.yml`, emit one more event into the same JSONL stream: sha,
ref, who/what triggered it, timestamp, whether `--build` ran. Five lines in
the workflow.

This is disproportionately valuable for what it costs:

- **Segmentation.** A reduced report can say "encoder p95 rose 40% after
  `<sha>`" instead of just "encoder p95 is 9s" — the only thing that turns a
  latency number into something actionable.
- **Explains discontinuities.** The gateway log reset on 3 Oct 18:42 because
  a deploy recreated the container — without a marker, that reads as traffic
  stopping, not as an infrastructure event.
- **It is the only record that carries causality.** No amount of aggregating
  latency numbers answers "what changed"; the marker is the one line that
  does.

## Step 6: PostHog — a different axis, joined, not merged in

PostHog measures the demand side: real users, how often, perceived latency
including network and rendering, who hits the 10-per-day quota. The
`[call]` stream measures the supply side: per-service latency on the
backend. Neither answers a useful question alone — "12 users, 3 abandoned
after 20s" needs "encoder p95 was 9s that day" needs "we shipped sha X that
morning" to actually point at a fix.

Two rules for how these combine:

- **The reduce step pulls from PostHog's query API** when building the
  weekly report; don't push server-side spans *into* PostHog. PostHog is
  built for event analytics, not for querying hundreds of per-hop
  latency records a week — the percentile tooling isn't the right shape for
  that, and it mixes two different kinds of data in one place for no gain.
- **PostHog is client-side-only and blind to the Revit/trial client.** The
  server-side JSONL stream is the only thing that sees both the web app and
  the Revit plugin, since both go through the same gateway. PostHog
  supplements the picture for the web app; it can never be the only source.

## Step 7: the weekly agentic job — build last, and only once there's volume

The Modal data showed roughly 8.3 runs/day over 17 days (peak day 46). At
that volume, steps 1–5 need time to accumulate before a weekly report has
enough to say anything. Building the job before there's data to read makes
it report "insufficient data" on a loop.

**Exception worth building early anyway: Modal capacity incidents.** The
four-minute queue stall on 24 Sep is exactly the kind of event nothing in the
stack currently detects, and it would show up even with only a handful of
runs that week. If step 3's Modal data starts flowing before the rest, a
narrow check — "did any call queue over N seconds this week" — is worth
having running on its own before the full report is built.

When the full job is built:

- **Always write the report** — as a published artifact, or committed under
  a docs path — even when nothing is wrong. Silence is not the same as "all
  clear" for a report whose entire job is to be checked.
- **Auto-opened GitHub issues only above a high bar**: a stated budget
  actually exceeded, the trend confirmed over two consecutive weeks (not one
  noisy data point), and a dedup check against already-open issues carrying
  the same label before creating a new one. Without that bar, the job
  produces the same issue every Monday and gets ignored.
- **A dedicated label** (e.g. `observability/auto`) so these can be bulk
  filtered or muted if the signal-to-noise ratio turns out wrong in practice.
- Use the `/schedule` skill for the cron-based cloud agent once this is
  ready to run unattended.

## Order to build

1. **DONE (PR #94):** `[call]` JSONL at all five `RemoteService` call sites,
   with service name from `cls.name` — plus the `asyncio.to_thread` fix in
   both fan-outs, without which correlation across them doesn't work.
2. `traceparent` propagation into the Modal app (or, cheaper first cut, pull
   from Modal's API in the reduce step).
3. Daily rotation to Object Storage.
4. The deploy marker in `deploy-scaleway.yml`.
5. The reducer, committed to the repo with tests. **Correction:** the
   original write-up said `concurrency.py` and `modal_stats.py` (built ad hoc
   during the Modal-log analysis) were in the repo to promote — they never
   were committed; the reducer is written from zero when this step comes up.
6. The weekly job — once 1–5 have enough days of real data behind them.

## Relationship to OpenTelemetry

OpenTelemetry is the right long-term shape for this — context propagation
via `traceparent` solves the correlation problem for free, and a client span
around the Modal call would have captured the queue-delay finding
automatically instead of requiring a manual dashboard export. It is not
worth adopting yet: at current volume, the time spent standing up a
collector and a backend costs more than it returns, and blanket
auto-instrumentation cuts against this codebase's explicit, no-hidden-control-flow
style (`CLAUDE.md`).

The reconciliation: build the `[call]` log lines at exactly the seams
OpenTelemetry would use — the same five call sites, the Flask request
entry, the same correlation id discipline. When OpenTelemetry is justified
by actual traffic, the migration is replacing the emit layer at seams already
cut correctly, not re-discovering where the seams should be.
