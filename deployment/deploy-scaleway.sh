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
#   bash deploy-scaleway.sh [--build] [--firewall]
#     --build      force rebuild of all images
#     --firewall   configure ufw on the instance to expose ONLY 22/80/443
#
# Prereqs on the instance: docker + docker compose v2, git.

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

FORCE_BUILD=false
SETUP_FIREWALL=false
for arg in "$@"; do
  case $arg in
    --build) FORCE_BUILD=true ;;
    --firewall) SETUP_FIREWALL=true ;;
    *) echo "Unknown option: $arg"; echo "Usage: bash deploy-scaleway.sh [--build] [--firewall]"; exit 1 ;;
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

# ── 1b. TLS: Cloudflare Origin Certificate ───────────────────────────────────
mkdir -p certs
if [[ ! -f certs/origin.pem || ! -f certs/origin.key ]]; then
  echo -e "${RED}Missing TLS cert${NC} (certs/origin.pem + certs/origin.key)."
  echo "Create a Cloudflare Origin Certificate (SSL/TLS ▶ Origin Server ▶ Create) and save:"
  echo "  - the certificate to deployment/certs/origin.pem"
  echo "  - the private key to deployment/certs/origin.key"
  echo "Then set Cloudflare SSL/TLS mode to 'Full (strict)'. See SCALEWAY_DEPLOYMENT.md."
  exit 1
fi

# ── 2. Clone/update the CPU microservices (no server_model — that's on Modal) ─
mkdir -p services
declare -a REPOS=(
  "server_obstruction:https://github.com/upskiller-xyz/server_obstruction.git"
  "server_encoder:https://github.com/upskiller-xyz/server_encoder.git"
  "server_merger:https://github.com/upskiller-xyz/server_merger.git"
  "server_stats:https://github.com/upskiller-xyz/server_stats.git"
)
echo -e "${BLUE}Cloning/updating microservices...${NC}"
for repo_info in "${REPOS[@]}"; do
  name="${repo_info%%:*}"; url="${repo_info#*:}"
  if [[ -d "services/$name/.git" ]]; then
    echo "  updating $name"; git -C "services/$name" pull --ff-only
  else
    echo "  cloning $name"; git clone --depth 1 "$url" "services/$name"
  fi
done

# ── 3. Optional firewall: expose only SSH + HTTP(S) ──────────────────────────
# Defence in depth on top of the Scaleway security group. The app services never
# bind host ports anyway, but this guarantees nothing else is reachable.
if [[ "$SETUP_FIREWALL" == true ]]; then
  echo -e "${BLUE}Configuring ufw (allow 22/80/443, deny the rest)...${NC}"
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw --force enable
fi

# ── 4. Bring up the stack ────────────────────────────────────────────────────
BUILD_FLAG=""; [[ "$FORCE_BUILD" == true ]] && BUILD_FLAG="--build"
echo -e "${BLUE}Starting stack...${NC}"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d $BUILD_FLAG

echo -e "${GREEN}Done.${NC} Public entrypoint: http://<instance-ip>/ (via nginx)."
echo "Internal services (encoder/obstruction/merger/stats/server-lux) are not host-published."
docker compose -f "$COMPOSE_FILE" ps
