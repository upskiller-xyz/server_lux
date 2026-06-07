#!/bin/bash
set -euo pipefail

# One-time VM bootstrap for the Scaleway container deployment.
# Installs Docker Engine + Compose v2 plugin + git on Ubuntu/Debian, and adds the
# current user to the docker group. Idempotent — safe to re-run.
#
# After this, log out/in once (for the docker group) and run:
#   bash deploy-scaleway.sh --build --firewall

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'

if [[ "$(id -u)" -ne 0 ]] && ! sudo -n true 2>/dev/null; then
  echo -e "${RED}Need root or passwordless sudo.${NC}"; exit 1
fi
SUDO=""; [[ "$(id -u)" -ne 0 ]] && SUDO="sudo"

echo -e "${GREEN}=== VM bootstrap: Docker + Compose + git ===${NC}"

# 1. Base packages
echo -e "${BLUE}Installing base packages...${NC}"
$SUDO apt-get update -y
$SUDO apt-get install -y ca-certificates curl gnupg git ufw jq openssl

# 2. Docker Engine + Compose plugin (official repo)
if ! command -v docker >/dev/null 2>&1; then
  echo -e "${BLUE}Installing Docker Engine...${NC}"
  $SUDO install -m 0755 -d /etc/apt/keyrings
  . /etc/os-release   # sets $ID (ubuntu/debian) and $VERSION_CODENAME
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    | $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
  $SUDO apt-get update -y
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo -e "${BLUE}Docker already installed — skipping.${NC}"
fi

# 3. Start on boot + add current user to docker group
$SUDO systemctl enable --now docker
if [[ "$(id -u)" -ne 0 ]]; then
  $SUDO usermod -aG docker "$USER" || true
  echo -e "${BLUE}Added $USER to the docker group — log out/in once for it to take effect.${NC}"
fi

echo -e "${GREEN}Done.${NC}"
docker --version
docker compose version
echo ""
echo "Next:"
echo "  cp .env.scaleway.example .env.scaleway && \$EDITOR .env.scaleway"
echo "  bash deploy-scaleway.sh --build --firewall"
