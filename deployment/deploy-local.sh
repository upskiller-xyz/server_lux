#!/bin/bash
set -e

# Local (no-auth) full-stack deployment for FRONTEND TESTING.
#
# Differences vs. deploy-full-stack.sh (the prod script):
#   - Does NOT clone/pull the microservice repos (assumes they already exist
#     under ./services from a previous deploy-full-stack.sh run).
#   - Layers docker-compose.local.yml on top to set AUTH_TYPE=none, so the
#     gateway accepts requests with no Authorization header.
#
# Everything runs as local containers: server-lux (:8080) plus obstruction,
# encoder, model, merger and stats on the internal Docker network.
#
# Usage: bash deploy-local.sh [--build]

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

FORCE_BUILD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --build) FORCE_BUILD=true; shift ;;
        *) echo "Unknown option: $1"; echo "Usage: bash deploy-local.sh [--build]"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d services/server_obstruction ]; then
    echo -e "${RED}services/ not found. Run 'bash deploy-full-stack.sh' once first to clone the microservices.${NC}"
    exit 1
fi

if docker compose version &> /dev/null; then DOCKER_COMPOSE="docker compose"; else DOCKER_COMPOSE="docker-compose"; fi

COMPOSE_FILES="-f docker-compose-full-stack.yml -f docker-compose.local.yml"
COMPOSE="$DOCKER_COMPOSE --env-file .env.full-stack $COMPOSE_FILES"

echo -e "${GREEN}=== Server Lux — LOCAL (no auth) deployment ===${NC}"

echo -e "${YELLOW}Stopping existing containers...${NC}"
$COMPOSE down 2>/dev/null || true

if [ "$FORCE_BUILD" = true ]; then
    echo -e "${YELLOW}Building all services (forced rebuild)...${NC}"
    $COMPOSE build --no-cache
else
    echo -e "${YELLOW}Building all services...${NC}"
    $COMPOSE build
fi

echo -e "${YELLOW}Starting all services...${NC}"
$COMPOSE up -d

echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

echo -e "${BLUE}Containers:${NC}"
docker ps --format '  {{.Names}}\t{{.Status}}'

echo ""
echo -e "${GREEN}Done.${NC} Frontend target: ${GREEN}http://localhost:8080${NC} (no auth)"
echo -e "  Smoke test:  ${GREEN}curl http://localhost:8080/${NC}"
echo -e "  Logs:        ${GREEN}$COMPOSE logs -f${NC}"
echo -e "  Stop all:    ${GREEN}$COMPOSE down${NC}"
