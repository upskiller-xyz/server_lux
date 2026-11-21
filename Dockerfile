# Gateway image on Project Hummingbird (Red Hat hardened, distroless Python).
#
# Two stages: the -builder image (has pip and a shell) builds a venv, and the
# distroless runtime image (no shell, no package manager, runs as UID 65532)
# only receives the venv and the source. Both are pinned by index digest
# (multi-arch); bump tag and digest together:
#   docker buildx imagetools inspect registry.access.redhat.com/hi/python:3.14
#   docker buildx imagetools inspect registry.access.redhat.com/hi/python:3.14-builder
#
# No OS packages are installed: OpenCV is the headless wheel, which needs no
# libGL/libX*, and the wheels bundle the native libraries they need.

FROM registry.access.redhat.com/hi/python:3.15-builder@sha256:41b08fc687e756ba1d099e14ab3595028ef4b1f649f328336cad74b318a539df AS build

# The builder image runs as 65532 too; installing into /opt needs root.
USER 0
RUN python3 -m venv /opt/venv
# Hash-locked requirements (generated from requirements.in); every artifact
# must match its pinned hash. pip is removed from the venv afterwards: nothing
# runs it at runtime, and it would only add scan findings.
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && /opt/venv/bin/pip uninstall --yes pip

FROM registry.access.redhat.com/hi/python:3.15@sha256:1739a8c22a807a31cb06a266747b72a276d8e416910a920941b168681a72420b

WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DEPLOYMENT_MODE=production

COPY --from=build /opt/venv /opt/venv
# Application source (root-owned, read-only for the app user; the app never
# writes to disk).
COPY src/ ./src/
COPY gunicorn.conf.py .

# Exec form: the runtime image has no shell. Any HTTP error fails the check.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/' % os.environ.get('PORT', '8080'), timeout=5)"]

EXPOSE 8080

# The image default (65532), stated explicitly so a base-image change cannot
# silently make the gateway run as root.
USER 65532

# Bind ($PORT), WORKERS (default 1) and THREADS (default 8) are read from the
# environment by gunicorn.conf.py, since exec form does no variable expansion.
CMD ["gunicorn", "-c", "/app/gunicorn.conf.py", "--timeout", "900", "--chdir", "src", "main:app"]
