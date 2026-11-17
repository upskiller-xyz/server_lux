"""Gunicorn settings resolved from the environment.

The runtime image is distroless (no shell), so the exec-form CMD cannot expand
$PORT, ${WORKERS:-1} or ${THREADS:-8}. This file does that instead; the
defaults match the previous shell-form CMD, and the compose files keep setting
PORT/WORKERS/THREADS as before.
"""

import os


class GunicornEnvSettings:
    """Reads the bind address and worker sizing from env vars."""

    BIND_TEMPLATE = "0.0.0.0:{port}"
    DEFAULT_PORT = "8080"
    DEFAULT_WORKERS = "1"
    DEFAULT_THREADS = "8"

    @classmethod
    def bind(cls) -> str:
        return cls.BIND_TEMPLATE.format(port=os.environ.get("PORT", cls.DEFAULT_PORT))

    @classmethod
    def workers(cls) -> int:
        return int(os.environ.get("WORKERS", cls.DEFAULT_WORKERS))

    @classmethod
    def threads(cls) -> int:
        return int(os.environ.get("THREADS", cls.DEFAULT_THREADS))


# Gunicorn reads these module-level names.
bind = GunicornEnvSettings.bind()
workers = GunicornEnvSettings.workers()
threads = GunicornEnvSettings.threads()
