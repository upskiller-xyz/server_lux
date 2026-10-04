# Plan: per-service deploys triggered by a tag

## Problem

`deploy-scaleway.sh` has two gaps that block "tag a service, deploy only that
service":

1. **No version pinning.** For each entry in `REPOS`, the script does
   `git clone --depth 1` or `git pull --ff-only` against the service repo's
   **default branch** (`deploy-scaleway.sh:70-75`). A tag on `server_encoder`
   has no effect on what the VM runs — the VM always runs whatever `master`
   currently points to, as of whenever someone last ran the deploy.
2. **No service granularity.** `--build` rebuilds the whole stack
   (`deploy-scaleway.sh:13,99`). There is no path to rebuild and restart one
   service in isolation.

Pinning is not a detail here — it is the precondition. Without it, "deploy on
a tag" degrades to "deploy whatever the default branch happens to be when
someone remembers to run the script." The ref has to be the thing a tag event
sets, or per-service granularity has nothing to attach to.

## Existing precedent

`obstruction-service` is already deployed separately, as its own Scaleway
Serverless Container, decoupled from this compose stack
(`docs/SCALEWAY_DEPLOYMENT.md`, the "Obstruction: off-box" section in
`deployment/docker-compose.scaleway.yml`). That split happened because
obstruction's CPU burst profile didn't fit sharing a fixed-core box with the
rest of the stack. It is the model to copy for *how to decouple a service's
deploy lifecycle* — not for *why* (the other services don't have obstruction's
burst problem), but for the shape of the solution: one service, one deploy
path, independent of the others.

## Known cost of per-service restarts

`server-lux` has `depends_on: <service>: condition: service_healthy` on every
backend service. A targeted `docker compose up -d --build encoder-service`
restarts only the encoder, but the gateway will see it go away and come back;
the encoder's healthcheck has `start_period: 40s`, so there is a real window —
seconds, not minutes, for a service that boots quickly — where gateway
requests touching the encoder see a 502. Acceptable for a low-traffic internal
tool; worth knowing before promising zero-downtime per-service deploys.

## Options, in increasing order of investment

### 1. Ref pinning (do this first, regardless of what else gets built)

Add one env var per service — `ENCODER_REF`, `MERGER_REF`, `MODEL_REF`,
`STATS_REF`, `OBSTRUCTION_REF` — default `master`. The clone/pull step in
`deploy-scaleway.sh` checks out that ref instead of pulling the default
branch:

```bash
git -C "services/$name" fetch --depth 1 origin "$ref"
git -C "services/$name" checkout --detach FETCH_HEAD
```

This alone makes deploys reproducible: the ref that is running is whatever is
written in `.env.scaleway`, not "whatever `master` was when the script last
ran." It costs nothing structurally and does not block any later option.

### 2. Targeted rebuild

The GitHub Actions workflow (`deploy-scaleway.yml`) gains an optional
`service` input. When set, the remote deploy step runs
`docker compose up -d --build <service>` instead of the full-stack command.
When unset, behavior is unchanged (full stack). This is the minimum change
that lets a human trigger "redeploy just the encoder."

### 3. `repository_dispatch` from each service repo

Each service repo (`server_encoder`, `server_merger`, …) gets a small
workflow: on push of a `v*` tag, send a `repository_dispatch` to `server_lux`
carrying `{service, ref}`. `server_lux`'s workflow reacts to the dispatch by
setting that service's `*_REF` and running the targeted rebuild from option 2.

This is the piece that actually answers "deploy on a tag, only the tagged
service." The reason to route through dispatch rather than giving each
service repo its own SSH key and copy of the deploy logic:
**`SCALEWAY_SSH_KEY` and the deploy script stay in exactly one place.** Five
repos with five copies of the key is five places to rotate it and five copies
of deploy logic that will drift from each other over time. One dispatch
receiver keeps the attack surface and the maintenance surface both at one.

### 4. Registry-based deploys (the step that changes the shape of the pipeline)

Instead of the VM building images from source, each service's own CI builds
the image on tag, pushes it to Scaleway Container Registry tagged with the
version (`v1.2.0`), and the VM's compose file references `image:
registry.../encoder:v1.2.0` instead of `build: ./services/server_encoder`.
Deploy becomes `docker compose pull encoder-service && up -d encoder-service`
— a pull, not a build.

Four reasons this is worth the larger investment:

- **Reproducibility.** The image running in production is bit-for-bit the one
  that was built and tested in CI, not a fresh build from whatever the ref
  resolved to at deploy time.
- **Rollback is a tag swap**, not a rebuild of old source.
- **The build leaves the VM.** The encoder image carries `torch` and
  `opencv`; building it on a 2-vCPU box is slow and steals CPU from whatever
  traffic is live during the build. This matters more than it looks like it
  should, given the encoder is one of the two services that actually do
  meaningful CPU work in the bundle (see the tracing plan — this is exactly
  the thing per-service spans would confirm or rule out).
- **It is the prerequisite for ever moving to serverless containers.**
  Serverless Containers take an image reference, not a build context. This
  work pays for itself even if the VM decision never changes, and is required
  if it does.

Cost: registry storage. `torch`/`opencv`-based images run 1–3 GB each — check
this against whatever free tier Scaleway Container Registry offers before
deciding how many tags to retain.

## Recommended order

1. **Ref pinning.** Zero new infrastructure, makes every existing deploy
   reproducible immediately.
2. **Targeted rebuild** via a workflow input. Lets a human redeploy one
   service without touching the others.
3. **`repository_dispatch` from each service repo.** This is what actually
   makes "tag a service → only that service redeploys" true end to end.
4. **Registry-based deploys**, once the compose file is being touched anyway
   for (2) and (3). Don't do this first — it's a bigger change and the first
   three options deliver the stated goal without it.

Steps 1–3 are maybe 40 lines of YAML and shell, achievable within a week.
Step 4 is the one worth scoping separately once 1–3 are live and the registry
question (cost, retention policy) has an answer.

## Open questions to resolve before implementing

- Scaleway Container Registry free-tier limits, if going for option 4.
- Whether `docker compose up -d --build <service>` without `--no-deps` will
  try to also recreate dependents due to `depends_on` — verify against the
  actual compose file before relying on it being scoped to one container.
- Who holds `SCALEWAY_SSH_KEY` today and whether `repository_dispatch` needs a
  new, narrower-scoped token (a `repo` dispatch token) in each service repo,
  separate from the deploy key itself.
