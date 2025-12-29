#!/bin/bash
set -e

# Full Stack Deployment Script for Server Lux + Microservices
# Usage: bash deploy-full-stack.sh [--build] [--debug]

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
FORCE_BUILD=false
DEBUG_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            FORCE_BUILD=true
            shift
            ;;
        --debug)
            DEBUG_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: bash deploy-full-stack.sh [--build] [--debug]"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Server Lux - Full Stack Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Navigate to deployment directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create services directory if it doesn't exist
mkdir -p services
cd services

# Clone or update microservices repositories
REPOS=(
    "server_obstruction:https://github.com/upskiller-xyz/server_obstruction.git"
    "server_encoder:https://github.com/upskiller-xyz/server_encoder.git"
    "server_model:https://github.com/upskiller-xyz/server_model.git"
    "server_merger:https://github.com/upskiller-xyz/server_merger.git"
    "server_stats:https://github.com/upskiller-xyz/server_stats.git"
)

echo -e "${BLUE}Cloning/updating microservices...${NC}"
for repo_info in "${REPOS[@]}"; do
    IFS=':' read -r repo_name repo_url <<< "$repo_info"

    if [ -d "$repo_name" ]; then
        echo -e "${YELLOW}  Updating $repo_name...${NC}"
        cd "$repo_name"
        git pull
        cd ..
    else
        echo -e "${YELLOW}  Cloning $repo_name...${NC}"
        git clone "$repo_url"
    fi
    echo -e "${GREEN}  ✓ $repo_name ready${NC}"
done

cd "$SCRIPT_DIR"

# Determine Docker Compose command
if command -v docker compose &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Stop existing containers
echo ""
echo -e "${YELLOW}Stopping existing containers...${NC}"
$DOCKER_COMPOSE -f docker-compose-full-stack.yml down 2>/dev/null || true

# Build services
if [ "$FORCE_BUILD" = true ]; then
    echo -e "${YELLOW}Building all services (forced rebuild)...${NC}"
    $DOCKER_COMPOSE -f docker-compose-full-stack.yml build --no-cache
else
    echo -e "${YELLOW}Building all services...${NC}"
    $DOCKER_COMPOSE -f docker-compose-full-stack.yml build
fi

# Start all services
echo ""
echo -e "${YELLOW}Starting all services...${NC}"
$DOCKER_COMPOSE -f docker-compose-full-stack.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check service health
echo ""
echo -e "${BLUE}Checking service health...${NC}"

SERVICES=(
    "server-lux:8080"
    "obstruction-service:8081"
    "encoder-service:8082"
    "model-service:8083"
    "merger-service:8084"
    "stats-service:8085"
)

ALL_HEALTHY=true
for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service_name port <<< "$service_info"

    if docker ps --format '{{.Names}}' | grep -q "^${service_name}$"; then
        if curl -s http://localhost:${port}/ > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓ ${service_name} (port ${port})${NC}"
        else
            echo -e "  ${YELLOW}⚠ ${service_name} (port ${port}) - running but not responding${NC}"
            ALL_HEALTHY=false
        fi
    else
        echo -e "  ${RED}✗ ${service_name} - not running${NC}"
        ALL_HEALTHY=false
    fi
done

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  Main Server:        ${GREEN}http://localhost:8080${NC}"
echo -e "  Obstruction:        ${GREEN}http://localhost:8081${NC}"
echo -e "  Encoder:            ${GREEN}http://localhost:8082${NC}"
echo -e "  Model:              ${GREEN}http://localhost:8083${NC}"
echo -e "  Merger:             ${GREEN}http://localhost:8084${NC}"
echo -e "  Stats:              ${GREEN}http://localhost:8085${NC}"
echo ""

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}✓ All services are healthy and responding${NC}"
else
    echo -e "${YELLOW}⚠ Some services may need more time to start${NC}"
    echo -e "${YELLOW}  Check logs: docker compose -f docker-compose-full-stack.yml logs${NC}"
fi

echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  View logs (all):     ${GREEN}docker compose -f docker-compose-full-stack.yml logs -f${NC}"
echo -e "  View logs (service): ${GREEN}docker logs -f <service-name>${NC}"
echo -e "  Stop all:            ${GREEN}docker compose -f docker-compose-full-stack.yml down${NC}"
echo -e "  Restart all:         ${GREEN}docker compose -f docker-compose-full-stack.yml restart${NC}"
echo -e "  View containers:     ${GREEN}docker ps${NC}"
echo ""
echo -e "${YELLOW}Test the API:${NC}"
echo -e "  ${GREEN}curl http://localhost:8080/${NC}"
echo ""
echo -e "${GREEN}Deployment successful!${NC}"
