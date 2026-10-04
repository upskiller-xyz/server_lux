# TLS certificates

nginx terminates HTTPS (`listen 443 ssl` in `../nginx-docker.conf`) using an
origin certificate mounted read-only at `/etc/nginx/certs/` from this directory
(see the `nginx` service in `../docker-compose.scaleway.yml`).

Drop two files here on the instance — **never commit them** (git-ignored):

| File | What |
|------|------|
| `origin.pem` | Certificate chain (PEM) |
| `origin.key` | Private key (PEM) |

## Cloudflare origin certificate (recommended)

Cloudflare → SSL/TLS → **Origin Server → Create Certificate** (15-year, free).
Set the Cloudflare SSL/TLS mode to **Full (strict)**. Save the cert as
`origin.pem` and the key as `origin.key` here.

```bash
# on the instance, in server_lux/deployment
install -m 700 -d certs
printf '%s\n' "<paste origin cert>" > certs/origin.pem
printf '%s\n' "<paste origin key>" > certs/origin.key
chmod 600 certs/origin.key
```

`git reset --hard` during CI deploy leaves these untracked files untouched, so
they persist across deploys.

## Self-signed (local testing only)

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout certs/origin.key -out certs/origin.pem -subj "/CN=localhost"
```
