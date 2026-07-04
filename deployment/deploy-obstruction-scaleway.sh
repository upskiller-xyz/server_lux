#!/usr/bin/env bash
#
# Deploy server_obstruction as a Scaleway Serverless Container.
#
# Why serverless: the obstruction workload is stateless, CPU-bound, bursty and
# embarrassingly parallel per request (64 directions). A fixed VM can't absorb
# the bursts (fixed CPU budget -> oversubscription -> thrash). Serverless with
# per-instance concurrency = 1 gives each request a dedicated instance and scales
# horizontally on burst.
#
# Pairs with server_lux backpressure: OBSTRUCTION_MAX_CONCURRENCY must equal
# MAX_SCALE below, and the container is PRIVATE (X-Auth-Token), matched by
# server_lux's ScalewayTokenAuth (SCW_CONTAINER_TOKEN).
#
# Prereqs: scw CLI configured (`scw init`), docker logged in to the Scaleway
# registry. Run:  bash deploy-obstruction-scaleway.sh
#
# VERIFY against current Scaleway docs before first run (values/flags drift):
#   - valid cpu-limit / memory-limit combos and the current per-container max
#   - the max allowed `timeout`
#   - that private containers use the `X-Auth-Token` header (matches lux)
set -euo pipefail

# ---- Config -----------------------------------------------------------------
REGION="${REGION:-fr-par}"
REGISTRY_NS="${REGISTRY_NS:-upskiller}"           # Scaleway Container Registry namespace
CONTAINER_NS="${CONTAINER_NS:-obstruction}"       # Serverless Containers namespace
CONTAINER_NAME="${CONTAINER_NAME:-obstruction}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Instance sizing (per the plan: 4 vCPU / 4 GB, concurrency=1).
CPU_LIMIT="${CPU_LIMIT:-4000}"                     # mvCPU (4000 = 4 vCPU)
MEMORY_LIMIT="${MEMORY_LIMIT:-4096}"              # MB
CONCURRENCY="${CONCURRENCY:-1}"                    # CPU-bound -> one request per instance
MIN_SCALE="${MIN_SCALE:-1}"                        # 1 warm instance kills cold starts
MAX_SCALE="${MAX_SCALE:-10}"                       # = server_lux OBSTRUCTION_MAX_CONCURRENCY
TIMEOUT="${TIMEOUT:-900s}"                         # matches gunicorn --timeout 900
PORT="${PORT:-8081}"                               # image binds gunicorn on :$PORT (ENV PORT 8081)

REGISTRY_HOST="rg.${REGION}.scw.cloud"
IMAGE="${REGISTRY_HOST}/${REGISTRY_NS}/obstruction:${IMAGE_TAG}"

# ---- 1. Build & push image to Scaleway Container Registry --------------------
# Serverless Containers pull from the Scaleway registry (not GCP Artifact Registry).
scw registry namespace create name="${REGISTRY_NS}" region="${REGION}" 2>/dev/null || true

# Build from the server_obstruction repo. The stack deploy no longer clones it
# (obstruction is off-box), so fetch it here if it isn't already present.
OBSTRUCTION_REPO="${OBSTRUCTION_REPO:-$(dirname "$0")/services/server_obstruction}"
OBSTRUCTION_GIT="${OBSTRUCTION_GIT:-https://github.com/upskiller-xyz/server_obstruction.git}"
if [ -d "${OBSTRUCTION_REPO}/.git" ]; then
  git -C "${OBSTRUCTION_REPO}" pull --ff-only
else
  git clone --depth 1 "${OBSTRUCTION_GIT}" "${OBSTRUCTION_REPO}"
fi
docker build -t "${IMAGE}" "${OBSTRUCTION_REPO}"
docker push "${IMAGE}"

# ---- 2. Serverless Containers namespace -------------------------------------
NS_ID="$(scw container namespace list region="${REGION}" name="${CONTAINER_NS}" -o json \
  | python3 -c 'import sys,json; ns=json.load(sys.stdin); print(ns[0]["id"] if ns else "")')"
if [ -z "${NS_ID}" ]; then
  NS_ID="$(scw container namespace create name="${CONTAINER_NS}" region="${REGION}" -o json \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
fi
echo "namespace: ${NS_ID}"

# ---- 3. Create/update the container -----------------------------------------
# privacy=private -> the platform gateway requires X-Auth-Token (see step 5).
# WORKERS=1 -> one gunicorn worker so the internal ThreadPoolManager (max(2,
# cpu-1) threads) owns the instance's cores without oversubscription. The floor
# of 2 means CPU_LIMIT should be >= 2 vCPU (2000 mvCPU) — 4 is recommended.
CONTAINER_ID="$(scw container container list region="${REGION}" namespace-id="${NS_ID}" name="${CONTAINER_NAME}" -o json \
  | python3 -c 'import sys,json; c=json.load(sys.stdin); print(c[0]["id"] if c else "")')"

COMMON_ARGS=(
  region="${REGION}"
  name="${CONTAINER_NAME}"
  registry-image="${IMAGE}"
  port="${PORT}"
  cpu-limit="${CPU_LIMIT}"
  memory-limit="${MEMORY_LIMIT}"
  min-scale="${MIN_SCALE}"
  max-scale="${MAX_SCALE}"
  max-concurrency="${CONCURRENCY}"
  timeout="${TIMEOUT}"
  privacy=private
  environment-variables.WORKERS=1
)

if [ -z "${CONTAINER_ID}" ]; then
  CONTAINER_ID="$(scw container container create namespace-id="${NS_ID}" "${COMMON_ARGS[@]}" -o json \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
  echo "created container: ${CONTAINER_ID}"
else
  scw container container update "${CONTAINER_ID}" "${COMMON_ARGS[@]}" >/dev/null
  echo "updated container: ${CONTAINER_ID}"
fi

# ---- 4. Deploy --------------------------------------------------------------
scw container container deploy "${CONTAINER_ID}" region="${REGION}" >/dev/null
ENDPOINT="$(scw container container get "${CONTAINER_ID}" region="${REGION}" -o json \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["domain_name"])')"
echo "endpoint: https://${ENDPOINT}"

# ---- 5. Invocation token (X-Auth-Token) -------------------------------------
# Generate once; store securely. server_lux sends it as X-Auth-Token via
# ScalewayTokenAuth (SCW_CONTAINER_TOKEN).
TOKEN="$(scw container token create container-id="${CONTAINER_ID}" region="${REGION}" -o json \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')"

cat <<EOF

============================================================================
Deployed. Wire server_lux to it (env):

  OBSTRUCTION_SERVICE_URL=https://${ENDPOINT}
  SCW_CONTAINER_TOKEN=${TOKEN}
  OBSTRUCTION_MAX_CONCURRENCY=${MAX_SCALE}

Notes:
  - Keep OBSTRUCTION_MAX_CONCURRENCY == max-scale (${MAX_SCALE}).
  - The URL host ends in .scw.cloud, so lux auto-selects ScalewayTokenAuth
    and attaches X-Auth-Token on both the JSON and binary obstruction calls.
  - This is orthogonal to lux's inbound Auth0 (different direction/header).
============================================================================
EOF
