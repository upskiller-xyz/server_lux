# Deployment Guide

This guide covers different deployment options for the Lux Server and its microservices.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Deployment Modes](#deployment-modes)
- [Local Development](#local-development)
- [Docker Compose Setup](#docker-compose-setup)
- [Production Deployment](#production-deployment)
- [Environment Configuration](#environment-configuration)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Lux Server is a gateway/orchestration service that coordinates requests across multiple microservices:

```
┌─────────────────┐
│   Lux Server    │  Main orchestration server
│   (port 8080)   │
└────────┬────────┘
         │
         ├─────────────┬─────────────┬──────────────┬──────────────┬──────────────┐
         │             │             │              │              │              │
    ┌────▼────┐  ┌────▼────┐  ┌─────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼──────┐
    │ Color   │  │Daylight │  │ Metrics   │  │Obstruc-  │  │ Encoder  │  │Postprocess│
    │ Manage  │  │  Model  │  │  /Eval    │  │ tion     │  │          │  │           │
    │ (8001)  │  │ (8002)  │  │  (8003)   │  │ (8004)   │  │ (8005)   │  │  (8006)   │
    └─────────┘  └─────────┘  └───────────┘  └──────────┘  └──────────┘  └───────────┘
```

### Microservices

| Service | Repository | Purpose | Port (Local) |
|---------|-----------|---------|--------------|
| Main (Lux) | [server_lux](https://github.com/upskiller-xyz/server_lux) | Orchestration & API Gateway | 8080 |
| Color Management | [server_color_management](https://github.com/upskiller-xyz/server_color_management) | RGB ↔ Values conversion | 8001 |
| Daylight Model | [server_model](https://github.com/upskiller-xyz/server_model) | Daylight factor simulation | 8002 |
| Metrics/Eval | [server_metrics](https://github.com/upskiller-xyz/server_metrics) | Statistical analysis | 8003 |
| Obstruction | [server_obstruction](https://github.com/upskiller-xyz/server_obstruction) | Horizon/zenith angle calculation | 8004 |
| Encoder | [server_encoder](https://github.com/upskiller-xyz/server_encoder) | Room parameter encoding | 8005 |
| Postprocess | [server_df_processing](https://github.com/upskiller-xyz/server_df_processing) | Result combination | 8006 |

---

## Deployment Modes

The server supports two deployment modes controlled by the `DEPLOYMENT_MODE` environment variable:

### Production Mode (`DEPLOYMENT_MODE=production`)
- Default mode
- Uses GCP Cloud Run URLs for all microservices
- Suitable for production deployments
- Each microservice is deployed independently on GCP

**Production URLs:**
```
Color Management: https://colormanage-server-182483330095.europe-north2.run.app
Daylight:        https://daylight-factor-182483330095.europe-north2.run.app
Metrics:         https://df-eval-server-182483330095.europe-north2.run.app
Obstruction:     https://obstruction-server-182483330095.europe-north2.run.app
Encoder:         https://encoder-server-182483330095.europe-north2.run.app
Postprocess:     https://daylight-processing-182483330095.europe-north2.run.app
```

### Local Mode (`DEPLOYMENT_MODE=local`)
- Uses Docker Compose service names
- All services run in containers on local machine
- Suitable for development and testing
- Services communicate via internal Docker network

**Local URLs (internal):**
```
Color Management: http://colormanage:8080
Daylight:        http://daylight:8080
Metrics:         http://metrics:8080
Obstruction:     http://obstruction:8080
Encoder:         http://encoder:8080
Postprocess:     http://postprocess:8080
```

---

## Local Development

### Prerequisites
- Python 3.11+
- pip

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/upskiller-xyz/server_lux.git
   cd server_lux
   ```

2. **Create virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   export DEPLOYMENT_MODE=production  # Uses production GCP services
   export PORT=8081
   export API_TOKEN=your_secret_token_here
   ```

5. **Run the server**
   ```bash
   python src/main.py
   ```

6. **Test the server**
   ```bash
   curl http://localhost:8081/
   ```

### Running Tests
```bash
# If tests are available
pytest tests/
```

### Interactive Demo
```bash
jupyter notebook example/demo.ipynb
```

---

## Docker Compose Setup

Run the complete microservices stack locally using Docker Compose.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/upskiller-xyz/server_lux.git
   cd server_lux
   ```

2. **Setup environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set your API token:
   ```bash
   DEPLOYMENT_MODE=local
   API_TOKEN=your_secret_token_here
   ```

3. **Authenticate with GCP**
   ```bash
   gcloud auth configure-docker europe-north2-docker.pkg.dev
   ```

   This configures Docker to authenticate with GCP Artifact Registry.

4. **Pull all service images**
   ```bash
   docker-compose pull
   ```

   This pulls pre-built images from GCP Artifact Registry:
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-colormanage-img:latest`
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-model-img:latest`
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-metrics-img:latest`
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-obstruction-img:latest`
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-encoder-img:latest`
   - `europe-north2-docker.pkg.dev/daylight-factor/daylight-server-docker-repo/daylight-postprocess-img:latest`

5. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Check service health**
   ```bash
   docker-compose ps
   ```

   All services should show `Up (healthy)` status.

6. **Test the main server**
   ```bash
   curl http://localhost:8080/
   ```

### Managing Services

**View logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f main
docker-compose logs -f encoder
```

**Restart a service:**
```bash
docker-compose restart main
```

**Stop all services:**
```bash
docker-compose down
```

**Stop and remove volumes:**
```bash
docker-compose down -v
```

**Rebuild and restart:**
```bash
docker-compose up -d --build
```

### Service Access

When running with Docker Compose:

**External Access (from host machine):**
- Main Server: http://localhost:8080
- Color Management: http://localhost:8001
- Daylight: http://localhost:8002
- Metrics: http://localhost:8003
- Obstruction: http://localhost:8004
- Encoder: http://localhost:8005
- Postprocess: http://localhost:8006

**Internal Access (between containers):**
- Services communicate using container names on port 8080
- Example: `http://encoder:8080/encode`

### Customizing Service URLs

If you need to customize service URLs, you can override them in `.env`:

```bash
# Custom local URLs
ENCODER_SERVICE_URL=http://my-custom-encoder:9000
DAYLIGHT_SERVICE_URL=http://my-custom-daylight:9001
```

---

## Production Deployment

### Deploying to GCP Cloud Run

Each microservice should be deployed separately to GCP Cloud Run.

#### Prerequisites
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- GCP project with billing enabled
- Container Registry or Artifact Registry enabled

#### Deploy Main Server

1. **Build the Docker image**
   ```bash
   docker build -t gcr.io/YOUR_PROJECT_ID/server-lux:latest .
   ```

2. **Push to Google Container Registry**
   ```bash
   docker push gcr.io/YOUR_PROJECT_ID/server-lux:latest
   ```

3. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy server-lux \
     --image gcr.io/YOUR_PROJECT_ID/server-lux:latest \
     --platform managed \
     --region europe-north2 \
     --allow-unauthenticated \
     --port 8080 \
     --set-env-vars DEPLOYMENT_MODE=production,API_TOKEN=your_secret_token \
     --memory 2Gi \
     --timeout 900
   ```

#### Deploy All Microservices

Repeat the above process for each microservice:

```bash
# Example for encoder service
cd ../server_encoder
docker build -t gcr.io/YOUR_PROJECT_ID/server-encoder:latest .
docker push gcr.io/YOUR_PROJECT_ID/server-encoder:latest

gcloud run deploy server-encoder \
  --image gcr.io/YOUR_PROJECT_ID/server-encoder:latest \
  --platform managed \
  --region europe-north2 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --timeout 300
```

#### Update Service URLs

After deploying all services, update the production URLs in [src/server/config.py](../src/server/config.py) with your Cloud Run service URLs.

Or use environment variables:
```bash
gcloud run services update server-lux \
  --set-env-vars ENCODER_SERVICE_URL=https://your-encoder-service.run.app
```

---

## Environment Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEPLOYMENT_MODE` | No | `production` | Deployment mode: `local` or `production` |
| `PORT` | No | `8080` | Port for the main server |
| `API_TOKEN` | Yes* | - | Authentication token for `/encode` endpoint |
| `COLORMANAGE_SERVICE_URL` | No | Auto | Override color management service URL |
| `DAYLIGHT_SERVICE_URL` | No | Auto | Override daylight service URL |
| `DF_EVAL_SERVICE_URL` | No | Auto | Override metrics service URL |
| `OBSTRUCTION_SERVICE_URL` | No | Auto | Override obstruction service URL |
| `ENCODER_SERVICE_URL` | No | Auto | Override encoder service URL |
| `POSTPROCESS_SERVICE_URL` | No | Auto | Override postprocess service URL |

\* Required only if using the `/encode` endpoint

### Configuration Files

- **`.env`** - Local environment variables (not committed to git)
- **`.env.example`** - Template for environment variables
- **`src/server/config.py`** - Service URL configuration logic
- **`docker-compose.yml`** - Docker Compose service definitions

---

## Troubleshooting

### Common Issues

#### Services not starting

**Check Docker daemon:**
```bash
docker ps
```

**Check logs:**
```bash
docker-compose logs
```

**Rebuild images:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Services unhealthy

**Check individual service health:**
```bash
docker exec server_encoder curl http://localhost:8080/
```

**Increase health check timeouts:**
Edit `docker-compose.yml` and increase `start_period`:
```yaml
healthcheck:
  start_period: 60s  # Give more time for startup
```

#### Connection refused errors

**Verify DEPLOYMENT_MODE:**
```bash
docker exec server_lux_main env | grep DEPLOYMENT_MODE
```

**Check network connectivity:**
```bash
docker exec server_lux_main ping colormanage
```

#### Port conflicts

**Find process using port:**
```bash
# Linux/Mac
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

**Use different ports:**
Edit `docker-compose.yml` and change port mappings:
```yaml
ports:
  - "9080:8080"  # Use 9080 externally instead of 8080
```

#### Permission denied on volumes

**Fix permissions:**
```bash
sudo chown -R $USER:$USER .
```

### Getting Help

- **Issues:** https://github.com/upskiller-xyz/server_lux/issues
- **Email:** info@upskiller.xyz
- **Documentation:** [docs/README.md](README.md)

### Debugging Tips

1. **Enable verbose logging:**
   ```bash
   export LOG_LEVEL=DEBUG
   ```

2. **Check service connectivity:**
   ```bash
   # From inside main container
   docker exec -it server_lux_main bash
   curl http://encoder:8080/
   ```

3. **Monitor resource usage:**
   ```bash
   docker stats
   ```

4. **Inspect service configuration:**
   ```bash
   docker inspect server_lux_main
   ```

---

## Additional Resources

- [API Documentation](api.md)
- [Microservices Documentation](microservices.md)
- [Development Guidelines](../CLAUDE.md)
- [Demo Notebook](../example/demo.ipynb)
