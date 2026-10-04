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
| Secret | `DEPLOY_VARS_TOKEN` | for tag deploys | Lets a tag deploy record its ref as a GitHub Variable — see [Per-service deploys](#per-service-deploys). Without it the pin is still kept on the box, just not durably |
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
   a single run by the tag in a `repository_dispatch`.
2. `deployment/services/.deployed-refs` on the box — what it last deployed for
   that service. The runtime `.env.scaleway` is rebuilt from scratch on every
   deploy, so this on-box record is what keeps a tag dispatch's pin from
   quietly reverting to `master` on the next unrelated deploy.
3. `master`.

The ref machinery covers the three CPU microservice checkouts (encoder,
merger, stats) — the only services whose source is pinned on the box. A
targeted `--service nginx` deploy touches no checkout, so it records no pins
and only restarts and revalidates the gateway.

A pin is recorded only after Compose has successfully deployed that ref, and
when the resolved ref differs from the recorded one the deploy forces a rebuild
— so the pin always describes the image that is actually running. This is
locked by behaviour tests (`deployment/tests/test-deploy-scaleway.sh`, run in
CI), not just stated here.

**A successful tag deploy writes (1) itself**, so the pin becomes the declared
answer rather than only a box-local side effect — and therefore survives the
instance being rebuilt. That write needs `DEPLOY_VARS_TOKEN`: a token allowed
to write Actions variables for the `prod` environment of this repo (confirm the
exact fine-grained permission name against GitHub's current docs when creating
it — the endpoint is `PUT /repos/{owner}/{repo}/environments/{env}/variables/{name}`).

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
- **From a tag on the service's own repo**, via `repository_dispatch`. A tag
  push on `server_encoder` (for example) sends a `service-tag` dispatch to
  this repo carrying `{"service": "encoder", "ref": "<tag>"}`; the workflow
  resolves that into `ENCODER_REF=<tag>` and `--service encoder-service`, and
  forces a rebuild (the whole point of the dispatch is new code to run).
  Dispatch refs — and the `ENCODER_REF` / `MERGER_REF` / `STATS_REF` GitHub
  Variables — are validated against `[A-Za-z0-9._/-]` before being used,
  since every one of them reaches a file the deploy script `source`s on the VM.

  The service repo needs a small workflow of its own — not committed here,
  since `server_lux` doesn't contain those repos' checkouts. For each of
  `server_encoder`, `server_merger`, `server_stats`, add
  `.github/workflows/dispatch-deploy.yml`:

  ```yaml
  name: Dispatch deploy to server_lux

  on:
    push:
      tags: ["v*"]

  jobs:
    dispatch:
      runs-on: ubuntu-latest
      steps:
        - name: Send service-tag dispatch
          env:
            # Fine-grained PAT (or GitHub App token) on
            # upskiller-xyz/server_lux with **Contents: write** — that is what
            # POST /repos/{owner}/{repo}/dispatches requires; Contents: read
            # plus Actions: write returns 403. NOT the default GITHUB_TOKEN,
            # which cannot dispatch across repositories.
            TOKEN: ${{ secrets.SERVER_LUX_DISPATCH_TOKEN }}
          run: |
            curl -fsS -X POST \
              -H "Authorization: Bearer $TOKEN" \
              -H "Accept: application/vnd.github+json" \
              https://api.github.com/repos/upskiller-xyz/server_lux/dispatches \
              -d "{\"event_type\":\"service-tag\",\"client_payload\":{\"service\":\"encoder\",\"ref\":\"${GITHUB_REF_NAME}\"}}"
  ```

  Change only `"service":"encoder"` per repo (`"merger"` / `"stats"`
  respectively) — everything else is identical across the three.

  **On the privilege this token carries.** The deploy key and all deploy logic
  stay in `server_lux`, so the service repos never hold SSH or Scaleway
  credentials. But `Contents: write` on `server_lux` is not a
  "trigger-this-workflow-only" permission — it also allows pushing to that
  repo. GitHub has no narrower scope for repository dispatch. Treat it
  accordingly: issue a dedicated token per service repo rather than sharing
  one, keep it out of every other workflow in that repo, and rotate it on the
  same schedule as the deploy key. A GitHub App installation token, restricted
  to `server_lux` and used only by this workflow, is the tighter option if the
  extra setup is worth it.

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
