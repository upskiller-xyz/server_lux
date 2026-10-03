# Fixtures for the gateway-config CI job

Stand-ins for Cloudflare's published range lists, pointed at by
`CLOUDFLARE_IPS_V4_URL` / `CLOUDFLARE_IPS_V6_URL` so
`update-cloudflare-ips.sh` regenerates deterministically and without network
access. The marker range `192.0.2.0/24` (RFC 5737 documentation space, never a
real Cloudflare range) lets CI assert that generation actually happened rather
than silently falling back to the committed snippet.

These are test inputs only — never deployed.
