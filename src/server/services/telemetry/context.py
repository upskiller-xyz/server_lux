from dataclasses import dataclass
from typing import Optional

from flask import Request, g

from .enums import TelemetryHeader

# Flask `g` key under which the auth layer stores the authenticated auth0 sub.
USER_SUB_KEY = "user_sub"


@dataclass
class TelemetryRequestContext:
    """Identity signals read from the inbound Flask request for telemetry.

    Single responsibility: pull user_sub (set by auth on `g`), session id and
    project id (forwarded headers) out of the request context.
    """

    user_sub: Optional[str] = None
    session_id: Optional[str] = None
    project_id: Optional[str] = None

    @classmethod
    def extract(cls, request: Request) -> "TelemetryRequestContext":
        return cls(
            user_sub=g.get(USER_SUB_KEY),
            session_id=request.headers.get(TelemetryHeader.SESSION_ID.value),
            project_id=request.headers.get(TelemetryHeader.PROJECT_ID.value),
        )
