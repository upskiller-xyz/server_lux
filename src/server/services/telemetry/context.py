from dataclasses import dataclass
from typing import Optional

from flask import Request, g

from .enums import TelemetryHeader

# Flask `g` key under which the auth layer stores the authenticated auth0 sub.
USER_SUB_KEY = "user_sub"

# Upper bound on any telemetry header value. Headers are unauthenticated caller input,
# so values are truncated before they travel further — the legitimate values (ids,
# semver-like versions) are far shorter, and an oversized one is a defect or an abuse.
MAX_HEADER_LENGTH = 64


@dataclass
class TelemetryRequestContext:
    """Identity signals read from the inbound Flask request for telemetry.

    Single responsibility: pull user_sub (set by auth on `g`) and the forwarded
    headers (session, project, client identity) out of the request context.
    """

    user_sub: Optional[str] = None
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    client_name: Optional[str] = None
    client_version: Optional[str] = None
    host_version: Optional[str] = None

    @classmethod
    def extract(cls, request: Request) -> "TelemetryRequestContext":
        return cls(
            user_sub=g.get(USER_SUB_KEY),
            session_id=cls._header(request, TelemetryHeader.SESSION_ID),
            project_id=cls._header(request, TelemetryHeader.PROJECT_ID),
            client_name=cls._header(request, TelemetryHeader.CLIENT_NAME),
            client_version=cls._header(request, TelemetryHeader.CLIENT_VERSION),
            host_version=cls._header(request, TelemetryHeader.HOST_VERSION),
        )

    @staticmethod
    def _header(request: Request, header: TelemetryHeader) -> Optional[str]:
        """Read one header, normalising absent, blank and oversized values to None/truncated.

        A blank header is treated as absent so it never reaches the payload as an
        empty string, which would be indistinguishable from a real value downstream.
        """
        value = (request.headers.get(header.value) or "").strip()
        return value[:MAX_HEADER_LENGTH] or None
