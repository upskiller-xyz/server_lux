# Docker Compose Quick Start Guide

This guide will help you run all microservices locally using Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0+)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (for pulling images)
- GCP access to the `daylight-factor` project

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/upskiller-xyz/server_lux.git
cd server_lux

# Copy environment template
cp .env.example .env

# Edit .env and set your API token
nano .env  # or use your preferred editor
```

**Required in `.env`:**
```bash
DEPLOYMENT_MODE=local
API_TOKEN=your_secret_token_here
```

### 2. Authenticate with GCP

```bash
# Authenticate with your GCP account
gcloud auth login

# Configure Docker to use GCP Artifact Registry
gcloud auth configure-docker europe-north2-docker.pkg.dev
```

### 3. Pull and Start Services

```bash
# Pull all service images (this may take a few minutes)
docker-compose pull

# Start all services in detached mode
docker-compose up -d
```

### 4. Verify Services

```bash
# Check service health
docker-compose ps

# Should show all services as "Up (healthy)"
```

### 5. Test the Main Server

```bash
# Test health endpoint
curl http://localhost:8080/

# Expected response:
# {"status": "running", "services": {...}}
```

## Service Ports

All services are accessible from your host machine:

| Service | Internal Port | External Port | URL |
|---------|--------------|---------------|-----|
| Main Server | 8080 | 8080 | http://localhost:8080 |
| Color Management | 8080 | 8001 | http://localhost:8001 |
| Daylight Simulation | 8080 | 8002 | http://localhost:8002 |
| Metrics/Evaluation | 8080 | 8003 | http://localhost:8003 |
| Obstruction Calc | 8080 | 8004 | http://localhost:8004 |
| Encoder | 8080 | 8005 | http://localhost:8005 |
| Postprocessing | 8080 | 8006 | http://localhost:8006 |

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f main
docker-compose logs -f encoder

# Last 100 lines
docker-compose logs --tail=100
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart main
```

### Stop Services

```bash
# Stop all services (keeps containers)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

### Update Images

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d
```

### Check Service Status

```bash
# List running containers
docker-compose ps

# Show resource usage
docker stats
```

## Docker Images

The following images are pulled from GCP Artifact Registry:

```
europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/
├── daylight-colormanage-img:latest
├── daylight-model-img:latest
├── daylight-metrics-img:latest
├── daylight-obstruction-img:latest
├── daylight-encoder-img:latest
└── daylight-postprocess-img:latest
```

You can override these in `.env`:

```bash
COLORMANAGE_IMAGE=europe-north2-docker.pkg.dev/.../daylight-colormanage-img:v1.2.3
ENCODER_IMAGE=europe-north2-docker.pkg.dev/.../daylight-encoder-img:v2.0.0
# etc.
```

## Troubleshooting

### Services not starting

**Check logs for errors:**
```bash
docker-compose logs
```

**Common issues:**
- Missing GCP authentication: Run `gcloud auth configure-docker europe-north2-docker.pkg.dev`
- Port conflicts: Check if ports 8080-8006 are already in use
- Insufficient resources: Ensure Docker has enough memory (recommend 4GB+)

### Services unhealthy

**Check individual service health:**
```bash
# From inside container
docker exec server_encoder curl http://localhost:8080/

# Check container logs
docker-compose logs encoder
```

**Increase startup time:**
Edit `docker-compose.yml` and increase `start_period`:
```yaml
healthcheck:
  start_period: 60s  # Give more time
```

### Cannot pull images

**Error: "access denied"**
```bash
# Re-authenticate
gcloud auth login
gcloud auth configure-docker europe-north2-docker.pkg.dev

# Verify access to GCP project
gcloud projects list
```

### Network issues

**Services can't communicate:**
```bash
# Check network
docker network ls
docker network inspect server_lux_microservices

# Restart networking
docker-compose down
docker-compose up -d
```

### Reset everything

**Complete cleanup:**
```bash
# Stop and remove everything
docker-compose down -v

# Remove images (optional)
docker-compose down --rmi all

# Start fresh
docker-compose pull
docker-compose up -d
```

## Architecture

```
┌─────────────────────────────────────┐
│   Docker Compose Network            │
│   (microservices)                   │
│                                     │
│  ┌──────────┐                       │
│  │   Main   │ ← http://localhost:8080
│  │  (8080)  │                       │
│  └────┬─────┘                       │
│       │                             │
│  ┌────┴────────────────────┐        │
│  │                         │        │
│  ▼                         ▼        │
│ ┌────────┐  ┌────────┐  ┌────────┐ │
│ │Encoder │  │Daylight│  │Obstruc │ │
│ │ (8005) │  │ (8002) │  │ (8004) │ │
│ └────────┘  └────────┘  └────────┘ │
│     ▲            ▲           ▲      │
│     │            │           │      │
│  External    External    External  │
│  :8005       :8002       :8004     │
└─────────────────────────────────────┘
```

**Internal Communication:**
- Services use container names: `http://encoder:8080`
- Docker DNS resolves service names to container IPs

**External Access:**
- Host machine accesses via mapped ports: `http://localhost:8005`

## Environment Variables

Full list in `.env`:

```bash
# Required
DEPLOYMENT_MODE=local          # Use local services
API_TOKEN=secret               # API authentication

# Optional - Override service URLs
COLORMANAGE_SERVICE_URL=http://colormanage:8080
DAYLIGHT_SERVICE_URL=http://daylight:8080
# ... etc

# Optional - Override Docker images
ENCODER_IMAGE=europe-north2-docker.pkg.dev/.../daylight-encoder-img:v1.0.0
# ... etc
```

## Performance Tips

1. **Allocate enough resources to Docker:**
   - Memory: 4GB minimum, 8GB recommended
   - CPUs: 2 minimum, 4 recommended

2. **Use Docker BuildKit for faster builds:**
   ```bash
   export DOCKER_BUILDKIT=1
   ```

3. **Prune unused resources regularly:**
   ```bash
   docker system prune -a
   ```

## Development Workflow

### Making changes to the main server

```bash
# Edit code in src/
nano src/server/services/orchestration.py

# Rebuild and restart main service
docker-compose up -d --build main

# View logs
docker-compose logs -f main
```

### Testing with production services

Switch between local and production:

```bash
# Use local services (Docker Compose)
export DEPLOYMENT_MODE=local

# Use production services (GCP Cloud Run)
export DEPLOYMENT_MODE=production
```

## Additional Resources

- [Full Deployment Guide](docs/deployment.md)
- [API Documentation](docs/api.md)
- [Microservices Overview](docs/microservices.md)
- [Demo Notebook](example/demo.ipynb)

## Getting Help

- **Issues:** https://github.com/upskiller-xyz/server_lux/issues
- **Email:** info@upskiller.xyz

---

**Quick Commands Reference:**

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f

# Status
docker-compose ps

# Restart
docker-compose restart

# Update
docker-compose pull && docker-compose up -d
```
