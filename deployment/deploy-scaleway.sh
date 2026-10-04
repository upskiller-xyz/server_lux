#!/bin/bash
set -euo pipefail

# Scaleway full-stack deployment: Modal inference + internal-only microservices.
#
# Runs the whole stack as Docker containers on a single Scaleway CPU Instance.
# nginx is the only service bound to host ports (80/443); every app service
# (including server-lux) lives only on the internal docker network. Inference is
# NOT a container here — server-lux calls Modal (set MODEL_SERVICE_URL + MODAL_*).
#
# Usage:
#   bash deploy-scaleway.sh [--build] [--firewall] [--service NAME]
#     --build          force rebuild of all images (or just --service's, if given)
#     --firewall       configure ufw on the instance to expose ONLY 22/80/443
#     --service NAME   restart/rebuild only this compose service, e.g.
#                       encoder-service. Uses --no-deps --force-recreate, so
#                       exactly one container restarts and it restarts even when
#                       nothing about it changed. Only that service's source
#                       checkout is re-pinned; the others are left exactly as
#                       they are, so a targeted deploy cannot move code that is
#                       not being redeployed.
#
# Each CPU microservice is pinned to a ref, resolved in this order:
#   1. <NAME>_REF in .env.scaleway (ENCODER_REF / MERGER_REF / STATS_REF) —
#      a GitHub Variable, or the tag carried by a repository_dispatch.
#   2. services/.deployed-refs — what this box last deployed for that service.
#   3. "master".
#
# Step 2 is what makes a pin survive. The CI deploy rebuilds .env.scaleway from
# scratch every run, so a ref supplied once (by a tag dispatch, say) is gone on
# the next deploy; without the on-box record the checkout would quietly return
# to master and the next rebuild would replace the tagged release.
#
# services/.deployed-refs also records the COMMIT each service was built from,
# and a commit that moved forces a rebuild. Tracking only the ref name would
# miss the common case: `master` advances and force-pushed tags keep their
# name, so the checkout changes while the name does not — and Compose would
# keep running the old image under a pin claiming it was current.
#
# Prereqs on the instance: docker + docker compose v2, git.

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

FORCE_BUILD=false
SETUP_FIREWALL=false
SERVICE_FILTER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) FORCE_BUILD=true; shift ;;
    --firewall) SETUP_FIREWALL=true; shift ;;
    --service)
      [[ $# -ge 2 ]] || { echo "--service requires a compose service name"; exit 1; }
      SERVICE_FILTER="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; echo "Usage: bash deploy-scaleway.sh [--build] [--firewall] [--service NAME]"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.scaleway.yml"
ENV_FILE=".env.scaleway"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Server Lux — Scaleway deployment (Modal inference)${NC}"
echo -e "${GREEN}========================================${NC}"

# ── 1. Env file ──────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}Missing $ENV_FILE${NC}. Copy the template and fill it in:"
  echo "  cp .env.scaleway.example $ENV_FILE && \$EDITOR $ENV_FILE"
  exit 1
fi

# Validate --service against the compose file itself (not a hardcoded list),
# so a typo or a renamed service fails here with a clear message instead of
# deep inside docker compose's own error output.
if [[ -n "$SERVICE_FILTER" ]]; then
  known_services="$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config --services)"
  # -F: the name is data, not a pattern. Without it "encoder-servic." matches
  # encoder-service and passes a check that promises exact validation.
  # --: a name starting with "-" is an argument, not an option.
  if ! grep -Fqx -- "$SERVICE_FILTER" <<< "$known_services"; then
    echo -e "${RED}Unknown --service '$SERVICE_FILTER'${NC}. Known services:"
    echo "$known_services" | sed 's/^/  /'
    exit 1
  fi
fi

# Sanity-check the Modal wiring early (fail before bringing the stack up).
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
if [[ "${MODEL_SERVICE_URL:-}" == *".modal.run"* ]]; then
  if [[ -z "${MODAL_KEY:-}" || -z "${MODAL_SECRET:-}" ]]; then
    echo -e "${RED}MODEL_SERVICE_URL is a Modal URL but MODAL_KEY/MODAL_SECRET are not set in $ENV_FILE${NC}"
    exit 1
  fi
  echo -e "${BLUE}Inference: Modal${NC} ($MODEL_SERVICE_URL)"
else
  echo -e "${YELLOW}Inference: MODEL_SERVICE_URL is not a *.modal.run URL — no proxy-auth will be attached.${NC}"
fi

# ── 2. Pin/update the CPU microservices to their configured ref ─────────────
# Not server_model (that's on Modal) and not server_obstruction (that's an
# off-box Scaleway Serverless Container, deployed from the server_obstruction repo).
mkdir -p services
declare -a REPOS=(
  "server_encoder:https://github.com/upskiller-xyz/server_encoder.git"
  "server_merger:https://github.com/upskiller-xyz/server_merger.git"
  "server_stats:https://github.com/upskiller-xyz/server_stats.git"
)

# What is currently deployed, per service, remembered ACROSS runs. The runtime
# .env.scaleway is rebuilt from scratch on every CI deploy, so a ref supplied
# once (e.g. by a tag dispatch) would otherwise vanish on the next deploy and
# the checkout would silently fall back to master — replacing a tagged release
# on the next rebuild. This file is the box's own record of its state; it lives
# under services/ which is gitignored.
#
# Pins are recorded only AFTER Compose has successfully deployed the ref (see
# the post-deploy step near the end), so the file always describes code that is
# actually running — never a ref whose build or start failed halfway.
PIN_FILE="services/.deployed-refs"

# Each service records two keys: "<short>=<ref>" (what to check out) and
# "<short>.commit=<sha>" (what was actually built). The ref answers "which
# branch/tag"; the commit answers "is the running image still current", which a
# ref name cannot — "master" and a force-moved tag both keep their name while
# pointing somewhere new. Reading "<short>" never picks up "<short>.commit"
# because the pattern is anchored on the "=" immediately after the name.
read_pin() {  # $1 = key (encoder | encoder.commit | …)
  [[ -f "$PIN_FILE" ]] || return 0
  # Last match wins, so a rewritten pin supersedes an older line.
  sed -n "s/^$1=//p" "$PIN_FILE" | tail -n 1
}

write_pin() {  # $1 = short name, $2 = ref
  local tmp="${PIN_FILE}.tmp"
  touch "$PIN_FILE"
  grep -v "^$1=" "$PIN_FILE" > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  mv "$tmp" "$PIN_FILE"
}

echo -e "${BLUE}Pinning microservices to their configured ref...${NC}"
# Pins staged here are written to $PIN_FILE only once the whole deploy has
# succeeded, and a checkout whose COMMIT differs from the recorded one forces a
# rebuild — without --build, Compose would restart the OLD image while the
# checkout sits on new code, and the pin would then describe code that never ran.
#
# The comparison is on the commit, not the ref name, because a ref name staying
# the same does not mean the code did: `master` moves, and a tag can be
# force-pushed to a new commit. Comparing names would call both of those
# "unchanged" and skip the rebuild. Comparing commits also avoids the opposite
# waste — retagging the same commit under a new name rebuilds nothing, since
# the image would be identical.
PENDING_PINS=()
# Services whose deploy was skipped as superseded (see the order check below).
STALE_SKIPPED=()
for repo_info in "${REPOS[@]}"; do
  name="${repo_info%%:*}"; url="${repo_info#*:}"
  short="${name#server_}"
  # On a targeted deploy, leave every other service's checkout alone. Re-pinning
  # all three here would move a checkout whose container is not being rebuilt,
  # so the next full rebuild would ship code nobody asked to deploy.
  if [[ -n "$SERVICE_FILTER" && "$SERVICE_FILTER" != "${short}-service" ]]; then
    continue
  fi
  # Precedence: an explicitly supplied <NAME>_REF (GitHub Variable, or the ref
  # carried by a tag dispatch) wins; else whatever this box last deployed; else
  # master, so a first deploy with nothing configured behaves as it always did.
  ref_var="$(echo "$short" | tr '[:lower:]' '[:upper:]')_REF"
  ref="${!ref_var:-}"
  [[ -n "$ref" ]] || ref="$(read_pin "$short")"
  [[ -n "$ref" ]] || ref="master"

  # Refuse a superseded release. A tag deploy carries <NAME>_ORDER, a counter
  # that only increases per service repo, and this compares it to the order
  # already deployed. The check has to live HERE, inside the deploy, not in the
  # workflow: the workflow's concurrency group serialises runs but GitHub does
  # not guarantee the order they execute in, so two tags pushed together can
  # arrive here newest-first. Without this, the older one would then win and
  # silently roll the service back.
  order_var="$(echo "$short" | tr '[:lower:]' '[:upper:]')_ORDER"
  order="${!order_var:-}"
  recorded_order="$(read_pin "${short}.order")"
  if [[ -n "$order" && -n "$recorded_order" && "$order" -lt "$recorded_order" ]]; then
    echo -e "${YELLOW}  $short: release $order is older than the deployed $recorded_order — skipping (superseded).${NC}"
    STALE_SKIPPED+=("$short")
    continue
  fi
  if [[ -d "services/$name/.git" ]]; then
    echo "  $name @ $ref"
    # Fetch exactly the configured ref (branch or tag — not a pull, since the
    # ref can move backwards between deploys, e.g. a rollback to an older tag)
    # and detach onto it, rather than trusting the branch already checked out.
    git -C "services/$name" fetch --quiet --depth 1 origin "$ref"
    git -C "services/$name" checkout --quiet --detach FETCH_HEAD
  else
    echo "  cloning $name @ $ref"
    git clone --quiet --depth 1 --branch "$ref" "$url" "services/$name"
  fi
  commit="$(git -C "services/$name" rev-parse HEAD)"
  recorded_commit="$(read_pin "${short}.commit")"
  if [[ "$commit" != "$recorded_commit" ]]; then
    # Covers a changed ref, a moved branch, a force-moved tag, and the first
    # deploy after this record was introduced (no commit stored yet).
    echo "  $short is at a new commit (${commit:0:12}) — forcing a rebuild so the image matches"
    FORCE_BUILD=true
  fi
  PENDING_PINS+=("$short=$ref" "${short}.commit=$commit")
  [[ -n "$order" ]] && PENDING_PINS+=("${short}.order=$order")
done

# A targeted deploy whose only target was superseded has nothing left to do.
# Returning before Compose matters: --force-recreate would otherwise restart the
# container that the NEWER release already put there, so a stale dispatch would
# still bounce a healthy service for no reason.
if [[ -n "$SERVICE_FILTER" && ${#STALE_SKIPPED[@]} -gt 0 ]]; then
  echo -e "${YELLOW}Nothing to deploy: $SERVICE_FILTER was superseded by a newer release.${NC}"
  echo "The newer release is already deployed; this run deliberately changed nothing."
  exit 0
fi

# ── 3. Refresh Cloudflare's published IP ranges ──────────────────────────────
# nginx restores each visitor's real IP from these ranges (per-IP rate limiting)
# and the origin lock only accepts connections from them. The script keeps the
# last known-good file on failure, so a deploy never hinges on Cloudflare
# being reachable.
echo -e "${BLUE}Refreshing Cloudflare IP ranges...${NC}"
bash nginx/update-cloudflare-ips.sh

# ── 4. Optional firewall: expose only SSH + HTTP(S) ──────────────────────────
# Defence in depth on top of the Scaleway security group. The app services never
# bind host ports anyway, but this guarantees nothing else is reachable.
if [[ "$SETUP_FIREWALL" == true ]]; then
  echo -e "${BLUE}Configuring ufw (allow 22/80/443, deny the rest)...${NC}"
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw --force enable
fi

# ── 5. Bring up the stack ────────────────────────────────────────────────────
BUILD_FLAG=""; [[ "$FORCE_BUILD" == true ]] && BUILD_FLAG="--build"
if [[ -n "$SERVICE_FILTER" ]]; then
  # --no-deps: restart exactly this container, not whatever it depends_on.
  # None of encoder/merger/stats declare their own depends_on today, so this
  # is a no-op in practice — kept so that stays true by construction, not by
  # accident, if one of them ever gains a dependency.
  #
  # --force-recreate: `up` leaves an existing container alone when neither its
  # config nor its image changed, so without this a targeted deploy without
  # --build could report success having restarted nothing. The contract here is
  # "this service restarts", so make that unconditional.
  echo -e "${BLUE}Starting stack (targeted: $SERVICE_FILTER)...${NC}"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps --force-recreate $BUILD_FLAG "$SERVICE_FILTER"
else
  echo -e "${BLUE}Starting stack...${NC}"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d $BUILD_FLAG
fi
# Validate the live config before reloading so a failed reload fails the deploy
# instead of leaving a stale edge policy behind while printing "Done". Only on a
# run that actually touches the gateway: a targeted encoder deploy must not fail
# on an unrelated pre-existing nginx config problem it did nothing to cause.
if [[ -z "$SERVICE_FILTER" || "$SERVICE_FILTER" == "nginx" ]]; then
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T nginx nginx -t
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T nginx nginx -s reload
fi

# ── 6. Record the deployed refs — only now that the deploy has succeeded ─────
# Compose is up (and the gateway validated, when this run touched it), so from
# here on a failure aborts before any pin is written. Writing pins earlier —
# right after the checkouts — would record refs whose build or start might
# still fail, and the file would claim code that is not running.
for pending in "${PENDING_PINS[@]}"; do
  write_pin "${pending%%=*}" "${pending#*=}"
done

echo -e "${GREEN}Done.${NC} Public entrypoint: http://<instance-ip>/ (via nginx)."
echo "Internal services (encoder/obstruction/merger/stats/server-lux) are not host-published."
docker compose -f "$COMPOSE_FILE" ps
