# Full Stack Deployment Guide

Deploy Server Lux with all microservices using Docker Compose.

## Overview

This deployment sets up the complete system:
- **Server Lux** (port 8080) - Main gateway server
- **Obstruction Service** (port 8081) - Calculates obstruction angles
- **Encoder Service** (port 8082) - Encodes room parameters
- **Model Service** (port 8083) - Runs daylight simulation
- **Merger Service** (port 8084) - Merges window results
- **Stats Service** (port 8085) - calculates stats

All services run in isolated Docker containers on a shared network.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0+)
- Git
- 8GB+ RAM recommended
- 10GB+ free disk space

## Quick Start

```bash
cd deployment
bash deploy-full-stack.sh
```

This will:
1. Clone all microservice repositories
2. Build Docker images for all services
3. Start all containers
4. Run health checks

## Deployment Options

### Standard Deployment
```bash
bash deploy-full-stack.sh
```

### Force Rebuild
Force rebuild all Docker images (useful after code changes):
```bash
bash deploy-full-stack.sh --build
```

### Debug Mode
Enable verbose logging (not yet implemented):
```bash
bash deploy-full-stack.sh --debug
```

## Architecture

```
┌─────────────────┐
│   Client        │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Server Lux     │ :8080
│  (Gateway)      │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┐
    │         │        │        │
    ▼         ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Obstr. │ │Encoder│ │ Model │ │Merger │
│ :8081 │ │ :8082 │ │ :8083 │ │ :8084 │
└───────┘ └───────┘ └───────┘ └───────┘
```

## Service Details

### Server Lux (Main Gateway)
- **Port:** 8080
- **Repository:** Current repository
- **Health Check:** `http://localhost:8080/`
- **Depends on:** All microservices

### Obstruction Service
- **Port:** 8081
- **Repository:** https://github.com/upskiller-xyz/server_obstruction
- **Health Check:** `http://localhost:8081/`
- **Function:** Calculates horizon/zenith angles from 3D meshes

### Encoder Service
- **Port:** 8082
- **Repository:** https://github.com/upskiller-xyz/server_encoder
- **Health Check:** `http://localhost:8082/`
- **Function:** Encodes room parameters to model input format

### Model Service
- **Port:** 8083
- **Repository:** https://github.com/upskiller-xyz/server_model
- **Health Check:** `http://localhost:8083/`
- **Function:** Runs ML-based daylight factor prediction

### Merger Service
- **Port:** 8084
- **Repository:** https://github.com/upskiller-xyz/server_merger
- **Health Check:** `http://localhost:8084/`
- **Function:** Merges results from multiple windows

### Stats Service
- **Port:** 8085
- **Repository:** https://github.com/upskiller-xyz/server_stats
- **Health Check:** `http://localhost:8085/`
- **Function:** Calculates the stats of the daylight factor in the apartment.

## Configuration

### Environment Variables

Edit `.env.full-stack` to configure:

```bash
# Number of worker processes per service
WORKERS=1

# Number of threads per worker
THREADS=8

# Deployment mode (local uses localhost URLs)
DEPLOYMENT_MODE=local

# Flask environment
FLASK_ENV=production
FLASK_DEBUG=False

# Logging level
LOG_LEVEL=INFO
```

### Network Configuration

All services communicate on the `lux-network` Docker bridge network. Services can reach each other using container names:
- `http://obstruction-service:8081`
- `http://encoder-service:8082`
- `http://model-service:8083`
- `http://merger-service:8084`
- `http://stats-service:8085`

## Management Commands

### View Logs

All services:
```bash
docker compose -f docker-compose-full-stack.yml logs -f
```

Specific service:
```bash
docker logs -f server-lux
docker logs -f obstruction-service
```

### Stop Services

```bash
docker compose -f docker-compose-full-stack.yml down
```

### Restart Services

All services:
```bash
docker compose -f docker-compose-full-stack.yml restart
```

Specific service:
```bash
docker compose -f docker-compose-full-stack.yml restart server-lux
```

### Check Status

```bash
docker compose -f docker-compose-full-stack.yml ps
```

### Execute Commands in Container

```bash
docker exec -it server-lux bash
docker exec -it obstruction-service bash
```

## Testing

### Health Check

```bash
# Check all services
curl http://localhost:8080/
curl http://localhost:8081/
curl http://localhost:8082/
curl http://localhost:8083/
curl http://localhost:8084/
```

### End-to-End Test

```bash
curl -X POST http://localhost:8080/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "df_default",
    "parameters": {
      "height_roof_over_floor": 2.7,
      "floor_height_above_terrain": 3.0,
      "room_polygon": [[0,0], [5,0], [5,4], [0,4]],
      "windows": {
        "main": {
          "x1": -0.6, "y1": 0.0, "z1": 0.9,
          "x2": 0.6, "y2": 0.0, "z2": 2.4,
          "window_frame_ratio": 0.15
        }
      }
    },
    "mesh": [[10,0,0], [10,0,5], [10,10,5], [10,10,0]]
  }'
```

## Troubleshooting

### Services Not Starting

1. Check Docker is running:
   ```bash
   docker info
   ```

2. Check available resources:
   ```bash
   docker system df
   ```

3. View service logs:
   ```bash
   docker compose -f docker-compose-full-stack.yml logs
   ```

### Port Conflicts

If ports 8080-8084 are already in use, modify `docker-compose-full-stack.yml`:

```yaml
ports:
  - "9080:8080"  # Change host port, keep container port
```

### Service Communication Issues

1. Check network:
   ```bash
   docker network inspect deployment_lux-network
   ```

2. Test connectivity from server-lux:
   ```bash
   docker exec -it server-lux curl http://obstruction-service:8081/
   ```

### Rebuild After Code Changes

```bash
# Stop services
docker compose -f docker-compose-full-stack.yml down

# Pull latest code
cd services/server_obstruction && git pull && cd ../..
cd services/server_encoder && git pull && cd ../..
cd services/server_model && git pull && cd ../..
cd services/server_merger && git pull && cd ../..

# Rebuild and restart
bash deploy-full-stack.sh --build
```

## Updating Services

### Update All Services

```bash
cd deployment/services

# Update each repository
for dir in server_*; do
  cd "$dir" && git pull && cd ..
done

# Rebuild
cd ..
bash deploy-full-stack.sh --build
```

### Update Single Service

```bash
cd deployment/services/server_obstruction
git pull
cd ../..

# Rebuild only that service
docker compose -f docker-compose-full-stack.yml build obstruction-service
docker compose -f docker-compose-full-stack.yml up -d obstruction-service
```

## Production Considerations

For production deployment:

1. **Use production-grade WSGI server** (already using Gunicorn)
2. **Set up SSL/TLS** with nginx reverse proxy
3. **Configure resource limits** in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 4G
   ```
4. **Enable monitoring** (Prometheus, Grafana)
5. **Set up log aggregation** (ELK stack, Loki)
6. **Configure backups** for any persistent data
7. **Use secrets management** for sensitive configuration

## Cleaning Up

Remove all containers, networks, and volumes:

```bash
docker compose -f docker-compose-full-stack.yml down -v
```

Remove downloaded service repositories:

```bash
rm -rf services/
```

## Security

### Overview

Server Lux uses a layered security model:

```
Internet
   │
   ▼
[Nginx]          ← Rate limiting, scanner blocking, security headers
   │
   ▼
[Server Lux]     ← Auth (token or Auth0 JWT) on all /v1/ endpoints
   │
   ▼
[Microservices]  ← Internal Docker network only, no external ports
```

### Authentication

Set `AUTH_TYPE` in `.env.full-stack`:

**Token-based (simple API key):**
```env
AUTH_TYPE=token
API_TOKEN=your-secret-token
```

All requests to `/v1/` must include:
```
Authorization: Bearer your-secret-token
```

**Auth0 (JWT, recommended for end users):**
```env
AUTH_TYPE=auth0
AUTH0_DOMAIN=your-tenant.eu.auth0.com
AUTH0_AUDIENCE=https://your-api
AUTH0_ALGORITHMS=RS256
```

Users obtain a token from Auth0 and send it as a Bearer token. See [Auth0 setup](#auth0-setup) below.

**No auth (local development only):**
```env
AUTH_TYPE=none
```

### Auth0 Setup

1. Create an **Auth0 Application** (your client app) and an **Auth0 API** (server_lux)
2. Disable self-signup in Auth0 dashboard — invite users manually
3. Optionally add a Post Login Action to whitelist specific users:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const allowedUsers = [
    "user1@example.com",
    "user2@example.com",
  ];
  if (!allowedUsers.includes(event.user.email)) {
    api.access.deny("Access not granted.");
  }
};
```

Users authenticate against Auth0 to receive a JWT, then use it as:
```bash
curl -X POST https://your-server/v1/simulate \
  -H "Authorization: Bearer <jwt-from-auth0>" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Network Isolation

Downstream microservices have no exposed ports — they are only reachable from within the `lux-network` Docker bridge network. Only server_lux can call them.

To verify:
```bash
# Should work (internal)
docker exec -it server-lux curl http://obstruction-service:8081/

# Should fail (no external port)
curl http://localhost:8081/
```

### Rate Limiting (Nginx)

Configured in `nginx-docker.conf`:
- `/v1/` endpoints: 30 requests/min per IP, burst of 5
- `/` (health check): 60 requests/min per IP, burst of 10
- Scanner paths (`.php`, `.env`, `/wp-admin`, etc.): dropped with `444` (no response)

### Autoheal

The `autoheal` container monitors all services and automatically restarts any container that goes unhealthy:

```bash
# Check autoheal logs
docker logs autoheal
```

### fail2ban (VM-level IP blocking)

fail2ban bans IPs that repeatedly trigger 444 or 429 responses from nginx.
Config files are in `deployment/fail2ban/`.

Install on the VM:
```bash
sudo apt install fail2ban

sudo cp deployment/fail2ban/filter.d/nginx-server-lux.conf /etc/fail2ban/filter.d/
sudo cp deployment/fail2ban/jail.d/nginx-server-lux.conf /etc/fail2ban/jail.d/

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

Verify it's running:
```bash
sudo fail2ban-client status nginx-server-lux
```

Manually unban an IP:
```bash
sudo fail2ban-client set nginx-server-lux unbanip <ip>
```

---

## Additional Resources

- [API Documentation](../docs/api.md)
- [Microservices Documentation](../docs/microservices.md)
- [Run Endpoint Schema](../docs/run_schema.md)
- [Main README](../README.md)
