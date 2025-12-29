# Local Deployment Guide

Deploy the full stack (all microservices) locally using Docker Compose.

## Prerequisites

- Docker
- Docker Compose
- Git

## Quick Start

### Option 1: Automated Script (Recommended)

```bash
cd deployment
bash deploy-full-stack.sh
```

The script will:
- Clone all microservice repositories
- Build all Docker images
- Start all services
- Verify health of all endpoints

### Option 2: Manual Deployment

1. **Navigate to deployment directory:**
   ```bash
   cd deployment
   ```

2. **Build all services:**
   ```bash
   docker-compose -f docker-compose-full-stack.yml build
   ```

3. **Start all services:**
   ```bash
   docker-compose -f docker-compose-full-stack.yml up -d
   ```

4. **Verify services are running:**
   ```bash
   docker-compose -f docker-compose-full-stack.yml ps
   ```

## Services

All services run on `localhost`:

| Service | Port | URL |
|---------|------|-----|
| Main Gateway | 8080 | http://localhost:8080 |
| Obstruction | 8081 | http://localhost:8081 |
| Encoder | 8082 | http://localhost:8082 |
| Model | 8083 | http://localhost:8083 |
| Merger | 8084 | http://localhost:8084 |
| Stats | 8085 | http://localhost:8085 |

## Check Health

```bash
curl http://localhost:8080/
```

Expected response:
```json
{
  "status": "running",
  "services": {
    "encoder": "ready",
    "merger": "ready",
    "model": "ready",
    "obstruction": "ready",
    "stats": "ready"
  }
}
```

## Stop Services

```bash
docker-compose -f docker-compose-full-stack.yml down
```

## View Logs

```bash
# All services
docker-compose -f docker-compose-full-stack.yml logs -f

# Specific service
docker-compose -f docker-compose-full-stack.yml logs -f server-lux
```

## Troubleshooting

### Services not communicating

If services show connection errors, ensure all containers are on the same network:
```bash
docker network ls
docker network inspect deployment_lux-network
```

### Port conflicts

If ports are already in use, modify the port mappings in `docker-compose-full-stack.yml`:
```yaml
ports:
  - "8080:8080"  # Change left side to different port
```

### Rebuild after code changes

```bash
docker-compose -f docker-compose-full-stack.yml build --no-cache
docker-compose -f docker-compose-full-stack.yml up -d
```

## Configuration

Environment variables are defined in `.env.full-stack`:

- `DEPLOYMENT_MODE=local` - Uses container names for inter-service communication
- `WORKERS=1` - Number of Gunicorn workers per service
- `THREADS=8` - Number of threads per worker

Service URLs are automatically configured for Docker network communication:
- `ENCODER_SERVICE_URL=http://encoder-service:8082`
- `MODEL_SERVICE_URL=http://model-service:8083`
- `MERGER_SERVICE_URL=http://merger-service:8084`
- `OBSTRUCTION_SERVICE_URL=http://obstruction-service:8081`
- `STATS_SERVICE_URL=http://stats-service:8085`

## Development Workflow

1. Make code changes
2. Rebuild affected service:
   ```bash
   docker-compose -f docker-compose-full-stack.yml build server-lux
   ```
3. Restart service:
   ```bash
   docker-compose -f docker-compose-full-stack.yml up -d server-lux
   ```
4. View logs:
   ```bash
   docker-compose -f docker-compose-full-stack.yml logs -f server-lux
   ```
