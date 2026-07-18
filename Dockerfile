FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade build tooling (fixes pip / setuptools / wheel CVEs), then purge the old
# bundled/cached wheels the base image ships (ensurepip stashes vulnerable
# pip/setuptools/wheel .whl files that scanners still flag even after an upgrade).
# The upgrade stays &&-gated so a failed upgrade fails the build; the cleanup runs
# in a best-effort block so every step runs regardless of the others' exit codes.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && { \
        find /usr/local/lib -type d -name "_bundled" -path "*ensurepip*" -exec rm -rf {} + 2>/dev/null; \
        rm -rf /root/.cache/pip; \
    }

# Copy requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV DEPLOYMENT_MODE=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/', timeout=5)" || exit 1

# Expose port
EXPOSE 8080

# Run with gunicorn (WORKERS/THREADS overridable via env; defaults match prior behavior)
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers ${WORKERS:-1} --threads ${THREADS:-8} --timeout 900 --chdir src main:app