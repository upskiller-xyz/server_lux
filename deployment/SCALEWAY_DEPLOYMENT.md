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
*build* to rebuild images).

### One-time GitHub configuration

Settings → Secrets and variables → Actions (under the `production` environment):

| Kind | Name | Purpose |
|------|------|---------|
| Secret | `MODAL_KEY`, `MODAL_SECRET` | Modal proxy-auth tokens |
| Secret | `API_TOKEN` | Public-API bearer token (when `AUTH_TYPE=token`) |
| Secret | `SCW_ACCESS_KEY`, `SCW_SECRET_KEY` | Scaleway creds (private bucket / registry) |
| Secret | `SCALEWAY_SSH_KEY` | Private SSH key authorized on the instance |
| Variable | `SCALEWAY_HOST`, `SCALEWAY_USER` | Instance address + SSH user |
| Variable | `DEPLOY_PATH` | server_lux checkout path on the box |
| Variable | `DEPLOY_REF` | Git ref to deploy (default `master`) |
| Variable | `MODEL_SERVICE_URL`, `AUTH_TYPE` | Non-secret runtime config |

Non-secret tunables (workers/CPUs/RAM) stay in the committed
[.env.scaleway.example](.env.scaleway.example); the workflow appends the secrets
on top of it.

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
- **Public API auth.** Set `AUTH_TYPE=token` + `API_TOKEN` to require a bearer
  token on the public API; default `none` (open).
