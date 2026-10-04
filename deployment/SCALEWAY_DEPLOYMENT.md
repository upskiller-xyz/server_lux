# Scaleway deployment — Modal inference + internal-only microservices

Runs the whole daylight stack as Docker containers on a **single Scaleway CPU
Instance**. GPU inference is no longer on-box — it runs on **Modal**, and
server-lux calls it over HTTPS.

## Topology

```
internet ──▶ nginx  (the ONLY published service: 80/443)
               └─▶ server-lux ──▶ encoder / obstruction / merger / stats   (internal only)
                              └─▶ MODEL_SERVICE_URL ──▶ Modal (GPU inference, off-box)
```

Only **nginx** binds host ports. Every app service — *including server-lux* — is
reachable only on the internal `lux-network` bridge, never from the host or the
internet. server-lux is exposed to the world solely through the nginx gateway
([nginx-docker.conf](nginx-docker.conf), which proxies `/`, `/v1/`, `/docs/` and
drops everything else).

## Why this shape

- **No cold start.** A single always-warm CPU instance; the cold-start tradeoff
  lives only on Modal (the GPU inference), which is the one bursty/expensive piece.
- **Inference outsourced.** The expensive GPU VM is gone; you pay Modal per
  inference and run a cheap CPU box for everything else.
- **Obstruction is the heaviest CPU service.** server-lux sends **one request per
  window**; the obstruction service computes all **64 directions internally**
  (vectorized ray casting). It gets the most CPU/RAM in the stack (see
  `OBSTRUCTION_*` in the env file).

## Files

| File | Purpose |
|------|---------|
| [docker-compose.scaleway.yml](docker-compose.scaleway.yml) | The stack: nginx + 4 CPU services, per-service resource limits. |
| [.env.scaleway.example](.env.scaleway.example) | Modal URL + creds, per-service workers/CPU/RAM. |
| [deploy-scaleway.sh](deploy-scaleway.sh) | Clone CPU services, sanity-check Modal wiring, bring the stack up. |
| [nginx-docker.conf](nginx-docker.conf) | The public gateway (reused as-is). |

## Deploy (CI-driven)

Deploys run from GitHub Actions — [deploy-scaleway.yml](../.github/workflows/deploy-scaleway.yml).
**Secrets live in GitHub Secrets** (the single source of truth); the workflow
renders them into the runtime `.env.scaleway` on the box and runs the deploy over
SSH. Nothing secret is committed, and nobody edits env files by hand on the box.

Trigger it manually: **Actions → Deploy to Scaleway → Run workflow** (tick
*build* to rebuild all images, or pick a single service in *service* to restart
only that one — see [Per-service deploys](#per-service-deploys) below).

### One-time GitHub configuration

Settings → Secrets and variables → Actions (under the `prod` environment):

| Kind | Name | Required? | Purpose |
|------|------|-----------|---------|
| Secret | `MODAL_KEY`, `MODAL_SECRET` | yes | Modal proxy-auth tokens |
| Secret | `SCALEWAY_SSH_KEY` | yes | Private SSH key authorized on the instance |
| Secret | `API_TOKEN` | when `AUTH_TYPE=token` | Public-API bearer token |
| Secret | `SCW_ACCESS_KEY`, `SCW_SECRET_KEY` | optional | Only for a private bucket / registry workflow — the default compose stack and `deploy-scaleway.sh` do **not** use them |
| Variable | `SCALEWAY_HOST`, `SCALEWAY_USER` | yes | Instance address + SSH user |
| Variable | `DEPLOY_PATH` | yes | server_lux checkout path on the box |
| Variable | `MODEL_SERVICE_URL` | yes | Modal endpoint (deploy fails fast if unset) |
| Variable | `DEPLOY_REF` | optional | Git ref to deploy (default `master`) |
| Variable | `AUTH_TYPE` | **required** | `auth0`, `token` or `none` — no default; deploy fails if unset |
| Variable | `CORS_ORIGINS` | recommended | Comma-separated browser origins allowed to call the API (the web app); empty = any origin |
| Variable | `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` | when `AUTH_TYPE=auth0` | Auth0 tenant + API identifier (public, not secrets) |
| Variable | `SSH_KNOWN_HOSTS` | **required** | Pinned host key (output of `ssh-keyscan <host>`, verified out of band); deploy fails if unset |
| Secret | `DEPLOY_VARS_TOKEN` | for tag deploys | Token with `Variables: Read and write` on this repo, so a tag deploy can record its ref as a repository Variable — see [Per-service deploys](#per-service-deploys). Without it the pin is still kept on the box, just not durably |
| Variable | `ENCODER_REF`, `MERGER_REF`, `STATS_REF` | optional | Per-service pin; normally written automatically by a tag deploy. Unset = fall back to the box's record, then `master` |

Non-secret tunables (workers/CPUs/RAM) stay in the committed
[.env.scaleway.example](.env.scaleway.example); the workflow appends the secrets
on top of it.

### Per-service deploys

`deploy-scaleway.sh --service <name>` restarts exactly one compose service
(`--no-deps --force-recreate`, so `depends_on` can't widen the blast radius
and the restart happens even when nothing about the container changed), and
re-pins only *that* service's source checkout — the others are left exactly
as they are, so a targeted deploy can never move code it isn't redeploying.

**How a service's ref is resolved**, in order:

1. `ENCODER_REF` / `MERGER_REF` / `STATS_REF` — from the GitHub Variables of
   the same name, which the workflow renders on **every** run, overridden for
   a single run by the `service_ref` input a tag deploy passes.
2. `deployment/services/.deployed-refs` on the box — what it last deployed for
   that service. The runtime `.env.scaleway` is rebuilt from scratch on every
   deploy, so this on-box record is what keeps a tag dispatch's pin from
   quietly reverting to `master` on the next unrelated deploy.
3. `master`.

The ref machinery covers the three CPU microservice checkouts (encoder,
merger, stats) — the only services whose source is pinned on the box. A
targeted `--service nginx` deploy touches no checkout, so it records no pins
and only restarts and revalidates the gateway.

A pin is recorded only after Compose has successfully deployed it, and the
deploy forces a rebuild whenever the checkout's **commit** differs from the
recorded one — so the pin always describes the image that is actually running.
The comparison is on the commit rather than the ref name because a name says
nothing about whether the code moved: `master` advances, and a tag can be
force-pushed. Each service therefore records both `<service>=<ref>` and
`<service>.commit=<sha>`. The converse also holds — retagging the same commit
under a new name rebuilds nothing, since the image would be identical.

All of this is locked by behaviour tests
(`deployment/tests/test-deploy-scaleway.sh`, run in CI), not just stated here.

**A successful tag deploy writes (1) itself**, so the pin becomes the declared
answer rather than only a box-local side effect — and therefore survives the
instance being rebuilt. That write needs `DEPLOY_VARS_TOKEN` with
**`Variables: Read and write`** on this repo.

These are **repository** variables, not environment ones, on purpose. Writing
an environment variable requires the `Environments` permission, which also
governs that environment's protection rules — a token with it could remove the
required reviewers gating this very deploy. `Variables` touches nothing but
variables. `vars.ENCODER_REF` still resolves, because lookup falls back from
environment to repository scope.

**Do not also define an environment-level `ENCODER_REF` / `MERGER_REF` /
`STATS_REF`.** It would shadow what the deploy writes, so a run would read a
stale pin while reporting a fresh one.

The write runs only after the deploy succeeds, so a Variable can never claim a
ref that is not actually running, and it is deliberately non-fatal: if the
token is missing or lacks permission, the run logs a warning and keeps the
on-box record. A tag deploy still works without the token — the pin is just no
longer durable, which is the state this whole mechanism exists to avoid, so
treat that warning as something to fix rather than noise.

Set a Variable by hand to pin a service without cutting a tag, or to roll back
to an earlier one.

Two ways to trigger:

- **Manually**: **Actions → Deploy to Scaleway → Run workflow**, pick a
  service in the *service* input. Redeploys that service at its current
  resolved ref — the Variable if set, otherwise the ref the box last
  deployed — without touching the others.
- **From a tag on the service's own repo.** A tag push on `server_encoder`
  (for example) triggers this workflow with
  `inputs: {service: encoder, service_ref: <tag>}`; it pins `ENCODER_REF` to
  that tag, runs `--service encoder-service --build`, and leaves the other
  services alone. A supplied `service_ref` is what forces the rebuild, so a
  tag deploy always ships new code while a manual run without one respects the
  *build* checkbox.

  Every ref is validated against `[A-Za-z0-9._/-]` plus the usual git ref-name
  rules before use — the dispatched one *and* the `ENCODER_REF` /
  `MERGER_REF` / `STATS_REF` Variables, since all of them reach a file the
  deploy script `source`s on the VM.

  The sending workflow lives in each service repo as
  `.github/workflows/deploy-on-tag.yml`
  ([encoder](https://github.com/upskiller-xyz/server_encoder/blob/master/.github/workflows/deploy-on-tag.yml),
  [merger](https://github.com/upskiller-xyz/server_merger/blob/master/.github/workflows/deploy-on-tag.yml),
  [stats](https://github.com/upskiller-xyz/server_stats/blob/master/.github/workflows/deploy-on-tag.yml)).
  They are identical apart from the service name; deliberately not copied into
  this document, so there is one place to change rather than two that drift.

  **The token they need: `SERVER_LUX_DISPATCH_TOKEN`, with `Actions: write` on
  this repo** — that is all `POST /repos/.../actions/workflows/{id}/dispatches`
  requires. The default `GITHUB_TOKEN` of another repo cannot dispatch here at
  all.

  This is why the trigger is `workflow_dispatch` and not `repository_dispatch`:
  the latter sits under `Contents: write`, which would also let a service
  repo's token push code to `server_lux`. Same capability, a token that cannot
  modify this repository.

  `Actions: write` is still not nothing — it can cancel or re-run other
  workflow runs here and delete their logs. The deploy key and the Scaleway
  credentials never leave `server_lux`, so a leaked sender token cannot reach
  the box directly, but issue one token per service repo rather than sharing
  one, keep it out of that repo's other workflows, and rotate it with the
  deploy key. A GitHub App installation token is the tighter option, and also
  survives the person who created it leaving the org.

### Manual deploy (fallback)

On a Scaleway CPU Instance with Docker + Compose v2:

```bash
git clone https://github.com/upskiller-xyz/server_lux.git
cd server_lux/deployment
cp .env.scaleway.example .env.scaleway
$EDITOR .env.scaleway          # set MODEL_SERVICE_URL + add the secrets yourself
bash deploy-scaleway.sh --build --firewall
```

`--build` rebuilds images; `--firewall` configures `ufw` to allow only 22/80/443.

## Instance sizing

Obstruction is the driver. A good starting point is a **4–8 vCPU / 16–32 GB** CPU
instance (e.g. Scaleway POP2-8C-32G): obstruction takes ~4 vCPU / 4 GB, the rest
share the remainder. Concurrency into obstruction ≈ (concurrent user requests) ×
(windows per request); each call computes 64 directions internally over the mesh.
Watch it under real load and adjust `OBSTRUCTION_WORKERS` / `OBSTRUCTION_CPUS` /
`OBSTRUCTION_MEM` (prod has run `WORKERS=32` for high concurrency). Workers above
the core count don't help — ray casting is CPU-bound.

## TLS (optional)

`nginx-docker.conf` listens on 80. For HTTPS, mount certs into the nginx service
(commented volume in the compose) and add a `listen 443 ssl;` server block, or
front the instance with a Scaleway Load Balancer that terminates TLS.

## Notes

- **No `server_model` container.** Inference is on Modal. To temporarily run
  inference on-box instead, point `MODEL_SERVICE_URL` at a container URL and add a
  `model-service` back from [docker-compose-full-stack.yml](docker-compose-full-stack.yml).
- **Modal proxy-auth is automatic.** A `*.modal.run` host is detected by
  server-lux and `Modal-Key`/`Modal-Secret` are attached from `MODAL_KEY` /
  `MODAL_SECRET`. The deploy script fails fast if the URL is Modal but creds are missing.
- **Public API auth.** `AUTH_TYPE` must be set explicitly: `auth0` (JWT),
  `token` (+ `API_TOKEN`, required) or `none` (open). No implicit default.
