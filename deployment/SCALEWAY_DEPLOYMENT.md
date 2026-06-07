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
([nginx-scaleway.conf](nginx-scaleway.conf), which terminates TLS, proxies `/`,
`/v1/`, `/docs/` and drops everything else).

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
| [nginx-scaleway.conf](nginx-scaleway.conf) | The public gateway: TLS + Cloudflare real-IP + rate limiting. |
| [certs/](certs/) | Cloudflare Origin cert (`origin.pem` + `origin.key`) — git-ignored. |

## Deploy

On a fresh Scaleway CPU Instance (Ubuntu/Debian, fr-par). Recommended type:
POP2-HC-8C-16G (~€155/mo) or STANDARD2-A4C-16G (~€85/mo for low traffic). Open
only 22/80/443 in the security group.

```bash
ssh root@<instance-ip>
git clone https://github.com/upskiller-xyz/server_lux.git
cd server_lux/deployment

bash setup-vm.sh               # one-time: installs Docker + Compose v2 + git + ufw

cp .env.scaleway.example .env.scaleway
$EDITOR .env.scaleway          # set MODEL_SERVICE_URL (the *.modal.run URL) + MODAL_KEY/MODAL_SECRET
bash deploy-scaleway.sh --build --firewall
```

`setup-vm.sh` is idempotent (skip if Docker is already installed). `--build`
rebuilds images; `--firewall` configures `ufw` to allow only 22/80/443.

## Instance sizing

Obstruction is the driver. A good starting point is a **4–8 vCPU / 16–32 GB** CPU
instance (e.g. Scaleway POP2-8C-32G): obstruction takes ~4 vCPU / 4 GB, the rest
share the remainder. Concurrency into obstruction ≈ (concurrent user requests) ×
(windows per request); each call computes 64 directions internally over the mesh.
Watch it under real load and adjust `OBSTRUCTION_WORKERS` / `OBSTRUCTION_CPUS` /
`OBSTRUCTION_MEM` (prod has run `WORKERS=32` for high concurrency). Workers above
the core count don't help — ray casting is CPU-bound.

## Domain + TLS (Cloudflare)

The gateway ([nginx-scaleway.conf](nginx-scaleway.conf)) terminates TLS on the
instance behind Cloudflare and restores the real client IP from
`CF-Connecting-IP`. Pattern: **Cloudflare proxied → origin over HTTPS with a
Cloudflare Origin Certificate** (15-year, free — no certbot/ACME in the container).

1. **DNS.** In Cloudflare, add an **A record** for your subdomain (e.g.
   `api.yourdomain.com`) → the instance's public IP, **Proxy status: Proxied**
   (orange cloud).
2. **Origin cert.** Cloudflare ▶ SSL/TLS ▶ **Origin Server** ▶ *Create Certificate*
   (cover `yourdomain.com` and `*.yourdomain.com`). Save the two PEM blocks on the
   instance as:
   - `deployment/certs/origin.pem` (the certificate)
   - `deployment/certs/origin.key` (the private key)

   (`deployment/certs/` is git-ignored — the key is never committed.)
3. **SSL/TLS mode.** Cloudflare ▶ SSL/TLS ▶ Overview ▶ set **Full (strict)**.
4. **Deploy.** `deploy-scaleway.sh` checks the cert exists before starting and
   nginx serves 443 with it; port 80 redirects to 443.

To rotate or move the domain later, just replace the files in `certs/` and
`docker compose -f docker-compose.scaleway.yml restart nginx`. `server_name` is a
catch-all (`_`), so no per-domain nginx edit is needed — Cloudflare routes by Host.

> Alternative (no Cloudflare): use Let's Encrypt via certbot like the legacy host
> deployment ([deploy.sh](deploy.sh)), or front the instance with a Scaleway Load
> Balancer that terminates TLS.

## Notes

- **No `server_model` container.** Inference is on Modal. To temporarily run
  inference on-box instead, point `MODEL_SERVICE_URL` at a container URL and add a
  `model-service` back from [docker-compose-full-stack.yml](docker-compose-full-stack.yml).
- **Modal proxy-auth is automatic.** A `*.modal.run` host is detected by
  server-lux and `Modal-Key`/`Modal-Secret` are attached from `MODAL_KEY` /
  `MODAL_SECRET`. The deploy script fails fast if the URL is Modal but creds are missing.
- **Public API auth.** Set `AUTH_TYPE=token` + `API_TOKEN` to require a bearer
  token on the public API; default `none` (open).
